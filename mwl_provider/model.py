from typing import cast
import hashlib
import sqlite3
import os
from abc import abstractmethod
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Table, Date, Time
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.engine.url import URL
from sqlalchemy.orm.exc import NoResultFound
from alembic.config import Config
from alembic import command
from fhir.resources.codesystem import CodeSystemConcept

from mwl_provider import logger
from mwl_provider.args_cache import ArgsCache
from mwl_provider.dicom.utils import make_code_sequence

from pydicom import Dataset

Base = declarative_base()

_NO_NAME_ = "[NO NAME]"

def populate_dataset(ds: Dataset, requested_modalities: list = []) -> Dataset|None:
    """ Populates the passed dataset with missing tags.

    Tags are looked up in the database, based on the procedure.

    Returns None if there is no requested procedure associated with the ExternalProcedure.code that matches the RequestedProcedureID.

    In order for a Dataset to be returned:

    - There must be a RequestedProcedureID in the Dataset ds
    - There must be a matching ExternalProcedure in the local DB
    - There must be an association between the ExternalProcedure and a RequestedProcedure in the local DB.
    """
    if not ds.RequestedProcedureID:
        logger.info(f"No RequestedProcedureID found from MWL coming from External Procedure.")
        return None

    session = get_session()
    external_procedure_id = None
    # Ideally, we would want to use the procedure id to lookup, as a code.
    if "RequestedProcedureCodeSequence" in ds:
        if len(ds.RequestedProcedureCodeSequence) > 0:
            external_procedure_id = ds.RequestedProcedureCodeSequence[0].CodeValue
    else:
        external_procedure_id = ds.RequestedProcedureID

    requested_procedure = None
    if external_procedure_id:
        # Lets lookup Requested Procedure by ID first.
        requested_procedure = get_requested_procedure_by_id(session, external_procedure_id)
    elif "RequestedProcedureDescription" in ds:
        # Let's try with description
        external_procedure_description = ds.RequestedProcedureDescription
        requested_procedure = get_requested_procedure_by_description(session, external_procedure_description)

    if requested_procedure:
        return requested_procedure.to_dicom_dataset(ds, requested_modalities)
    else:
        logger.debug(f"No match found for {external_procedure_id}")
        return None

  
def database_exists_and_valid():
    args = ArgsCache.get_arguments()
    # Check if file exists
    if not os.path.exists(args.database_file):
        logger.debug(f"Database file {args.database_file} does not exist.")
        return False
    
    # Check if the file is empty
    if os.path.getsize(args.database_file) == 0:
        logger.debug(f"Database file {args.database_file} exists and is empty.")
        return False
    
    # Check if the file is a valid SQLite database
    try:
        conn = sqlite3.connect(args.database_file)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        logger.debug(f"Database file {args.database_file} exists and is valid.")
        return True
    except sqlite3.DatabaseError:
        logger.debug(f"Database file {args.database_file} exists not empty, but not an sqlite3 DB.")
        return False


def init_database(engine=None):
    print(f"init_database: Logger level {logger.getEffectiveLevel()}")
    if not engine:
        engine = get_engine()
    logger.debug(f"Preparing to initialize Database {engine.url}")

    # Configure Alembic
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.attributes['configure_logger'] = False
    alembic_cfg.set_main_option('sqlalchemy.url', str(engine.url))

    # Apply migrations to the latest revision
    command.upgrade(alembic_cfg, "head")
    logger.debug(f"Database {engine.url} initialized with Alembic migrations")

def get_engine_url() -> URL:
    """ Return the URL for this engine.
    
    Created for Alembic, used in env.py.
    """
    args = ArgsCache.get_arguments()
    database_path = os.path.abspath(args.database_file)
    return URL.create(
        drivername='sqlite',
        database=database_path
    )

def get_engine(url=None):
    if not url:
        url = get_engine_url()
    return create_engine(url)

def get_session_factory(engine):
    return sessionmaker(bind=engine)

def get_session(engine=None):
    """ Single Wrapper Function to get a session.
    
    This is the easiest way to get a session. Just import this function, then 

    session = get_session()
    """
    if not engine:
        engine = get_engine()
    session_factory = get_session_factory(engine)

    return session_factory()

scheduled_protocols_association = Table(
    'scheduled_protocols_association', Base.metadata,
    Column('procedure_step_id', Integer, ForeignKey('scheduled_procedure_steps.id')),
    Column('protocol_id', Integer, ForeignKey('scheduled_protocols.id'))
)

requested_procedure_steps_association = Table(
    'requested_procedure_steps_association', Base.metadata,
    Column('requested_procedure_id', Integer, ForeignKey('requested_procedures.id')),
    Column('procedure_step_id', Integer, ForeignKey('scheduled_procedure_steps.id'))
)


class ExternalProcedure(Base):
    ''' The proceedure that comes from the external Practice Management System.'''
    __tablename__ = 'external_procedures'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, default=_NO_NAME_)
    system = Column(String, comment="Name or URL of the external system.")
    code = Column(String)
    description = Column(String)
    short_name = Column(String)
    requested_procedure_id = Column(Integer, ForeignKey('requested_procedures.id'))  # This must point to the primary key of RequestedProcedure

    requested_procedure = relationship(
        "RequestedProcedure", back_populates="external_procedures")

    def __init__(self, tops_procedure:ProcedureType=None, **kwargs):
        if tops_procedure is not None:
            self.from_tops_procedure(tops_procedure=tops_procedure)
        super(ExternalProcedure, self).__init__(**kwargs)

    def __str__(self):
        return self.name

    def from_tops_procedure(self, tops_procedure:ProcedureType):
            self.code = tops_procedure.type_id
            self.system = 'http://topsortho.com/topsdb'
            self.name = tops_procedure.type_label
            self.short_name = tops_procedure.short_label
            self.description = tops_procedure.permanent_label

class CodeMixin():
    code_value = Column(String)
    code_scheme = Column(String)
    code_meaning = Column(String)

    def __str__(self):
        return self.name or "No Code Meaning"

    def from_concept(self, concept: CodeSystemConcept):
        """Update from a FHIR CodeSystemConcept."""
        self.code_value = concept.code
        self.code_meaning = concept.display
        self.name = concept.display
        # Get system from concept parent codesystem if available
        if hasattr(concept, '_parent'):
            self.code_scheme = concept._parent.url
        else:
            self.code_scheme = 'unknown'

    # Replace legacy from_code with from_concept for simplicity
    def from_code(self, concept: CodeSystemConcept, session=None):
        """Kept for backwards compatibility, just calls from_concept."""
        self.from_concept(concept)

    @abstractmethod
    def to_dicom_dataset(self, ds: Dataset = None) -> Dataset:
        """ Convert to a DICOM Dataset.
        
        If ds is passed, the passed dataset will be used as base, and tags will be added.
        
        """
        pass

class RequestedProcedure(Base,CodeMixin):
    __tablename__ = 'requested_procedures'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, default=_NO_NAME_)
    comments = Column(String)
    description = Column(String)
    requesting_physician_name = Column(String)
    # Relationship to link back to external procedures
    external_procedures = relationship(
        "ExternalProcedure", back_populates="requested_procedure")

    # Many-to-many relationship with ScheduledProcedureStep
    scheduled_procedure_steps = relationship(
        "ScheduledProcedureStep",
        secondary=requested_procedure_steps_association,
        back_populates="requested_procedures"
    )

    def to_dicom_dataset(self, ds:Dataset = None, requested_modalities: list = []) -> Dataset:
        """ Return a Requested Procedure Dataset.
        
        Use the data from this RequestedProcedure to populate the passed ds Dataset. Scheduled Procedure Steps are added to any existing ones in the passed ds Dataset.

        If no requested modalities are passed, then all ScheduledProcedureSteps are added.
        """
        if not ds:
            ds = Dataset()

        if self.comments:
            ds.RequestedProcedureComments = self.comments
        else:
            ds.RequestedProcedureComments = self.name

        if self.description:
            ds.RequestedProcedureDescription = self.description
        
        if self.code_value:
            ds.RequestedProcedureCodeSequence = [
                make_code_sequence(
                    code=self.code_value, 
                    prefix=self.code_scheme,
                    display=self.code_meaning)
                ]

        if self.requesting_physician_name:
            ds.RequestingPhysician = self.requesting_physician_name

        found_modalities = [] # A list of all different types of modalities found in this Requested Procedure. Used to create a unique Req. Proc. Id.
        if self.scheduled_procedure_steps:
            # If an existing one is found, then use the data from that one, by passing it to the to_dicom_dataset of ScheduledProcedureStep.
            if not ds.ScheduledProcedureStepSequence:
                ds.ScheduledProcedureStepSequence = []
                existing_sps = None
            else:
                existing_sps = ds.ScheduledProcedureStepSequence[0]
            ds.ScheduledProcedureStepSequence = [] # reset the sequence
            for step in self.scheduled_procedure_steps:
                step = cast(ScheduledProcedureStep, step)
                # Only add the step if its one of the requested modalities or if requested_modalities is empty or contains an empty string.
                if not requested_modalities or requested_modalities == [''] or step.modality in requested_modalities:
                    found_modalities.append(step.modality)
                    ds.ScheduledProcedureStepSequence.append(step.to_dicom_dataset(existing_sps)) # Add new with new template.

        if found_modalities:
            # At the last minute, add a unique 
            # RequestedProcedureID = hash(modalities + AccessionNumber + RequestedProcedureID)
            rpIDstr = f"{''.join(found_modalities)}{ds.AccessionNumber}{self.id}"
            ds.RequestedProcedureID = hashlib.md5(rpIDstr.encode()).hexdigest()[:16]
            return ds
        else:
            return None


class ScheduledProcedureStep(Base, CodeMixin):
    ''' The procedure that will be used to produce the DICOM MWL.'''
    __tablename__ = 'scheduled_procedure_steps'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, default=_NO_NAME_)
    station_ae_title = Column(String)
    start_date = Column(Date)
    start_time = Column(Time)
    location = Column(String)
    modality = Column(String)
    performing_physicians_name = Column(String)

    # Many-to-many relationship with ProcedureSteps
    protocols = relationship(
        "ScheduledProtocol",
        secondary=scheduled_protocols_association,
        back_populates="procedures"
    )

    # Many-to-many relationship with RequestedProcedure
    requested_procedures = relationship(
        "RequestedProcedure",
        secondary=requested_procedure_steps_association,
        back_populates="scheduled_procedure_steps"
    )


    def to_dicom_dataset(self, ds:Dataset = None) -> Dataset:
        """ Return a Scheduled Procedure Step Dataset.
        
        Scheduled Protocol Code Sequence are added to any exising ones in the passed ds Dataset.

        NB: The ScheduledProcedureStep does not include a Code Sequence.
        """
        if not ds:
            ds = Dataset()
        if self.name:
            ds.ScheduledProcedureStepDescription = self.name

        ds.ScheduledProcedureStepID = f"{self.code_scheme}-{self.code_value}"[:16]

        ds.Modality = self.modality

        if self.station_ae_title:
            ds.ScheduledStationAETitle = self.station_ae_title
        
        if self.performing_physicians_name:
            ds.ScheduledPerformingPhysicianName = self.performing_physicians_name

        if self.protocols:
            if not hasattr(ds,'ScheduledProtocolCodeSequence'):
                ds.ScheduledProtocolCodeSequence = []
            for protocol in self.protocols:
                protocol = cast(ScheduledProtocol, protocol)
                ds.ScheduledProtocolCodeSequence.append(protocol.to_dicom_dataset())

        return ds

    def __str__(self):
        return self.name if self.name else f"Scheduled Procedure Step {self.id}"

    def from_concept(self, concept: CodeSystemConcept):
        """Update from FHIR CodeSystemConcept."""
        super().from_concept(concept)
        # Set modality based on URL pattern - could be made more sophisticated
        if 'photographic' in concept._parent.url:
            self.modality = 'XC'
        elif 'visible-light' in concept._parent.url:
            self.modality = 'VL'


class ScheduledProtocol(Base,CodeMixin):
    __tablename__ = 'scheduled_protocols'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, default=_NO_NAME_)

    # Many-to-many relationship with ScheduledProcedureStep
    procedures = relationship(
        "ScheduledProcedureStep",
        secondary=scheduled_protocols_association,
        back_populates="protocols"
    )

    def __init__(self, concept: CodeSystemConcept = None, **kwargs):
        if concept is not None:
            self.from_concept(concept)
        super(ScheduledProtocol, self).__init__(**kwargs)

    def to_dicom_dataset(self, ds:Dataset = None) -> Dataset:
        """ Returns a Code Sequence Containing this Scheduled Protocol.
        
        Passed ds is ignored.
        """
        return make_code_sequence(
            code=self.code_value,
            prefix=self.code_scheme,
            display=self.code_meaning
        )

# Must come after RequestedProcedure
# Cannot go in utils, becuase it relies on model, which relies on utils: circular imports.
def get_requested_procedure_by_id(session, external_procedure_id) -> RequestedProcedure:
    """ Return the RequestedProcedure that matches external_procedure id.
    
    It is required to go look at the ExternalProcedures code.
    """
    return session.query(RequestedProcedure).\
        join(ExternalProcedure).\
        filter(ExternalProcedure.code == external_procedure_id).\
        first()

def get_requested_procedure_by_description(session, external_procedure_description) -> RequestedProcedure:
    """ Return the RequestedProcedure that matches external_procedure id.
    
    It is required to go look at the ExternalProcedures code.
    """
    return session.query(RequestedProcedure).\
        join(ExternalProcedure).\
        filter(ExternalProcedure.description == external_procedure_description).\
        first()
