from typing import cast
import sys
import signal
import logging
import requests
from fhir.resources.codesystem import CodeSystem, CodeSystemConcept
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(funcName)s: %(message)s')

from sqlalchemy import and_
from topsserver_db.clinical import ProcedureTypeManager
from topsserver_db.models.topsdb import ProcedureType

# Used dynamically in the code via globals(). Do not remove.
from tops_dicom.model import ScheduledProtocol, ScheduledProcedureStep

from tops_dicom import logger, MWL_PREFIX
from tops_dicom.constants import verbosity_mapping
from tops_dicom.model import ExternalProcedure, get_session, database_exists_and_valid, init_database
from tops_dicom.args_cache import ArgsCache

# Define your code systems URLs
CODESYSTEM_URLS = [
    "http://terminology.open-ortho.org/fhir/extraoral-2d-photographic-scheduled-protocol",
    "http://terminology.open-ortho.org/fhir/intraoral-2d-photographic-scheduled-protocol",
    "http://terminology.open-ortho.org/fhir/extraoral-3d-visible-light-scheduled-protocol",
    "http://terminology.open-ortho.org/fhir/intraoral-3d-visible-light-scheduled-protocol",
    "http://terminology.open-ortho.org/fhir/ada-1100-enumerated-terms",
    "http://terminology.open-ortho.org/fhir/dentaleyepad-image-types",
]

def import_procedures(session, topsdb_config):
    args = ArgsCache.get_arguments()
    
    if not args.procedure_type_prefix:
        procedure_type_prefix = MWL_PREFIX
    else:
        procedure_type_prefix = args.procedure_type_prefix

    pmt = ProcedureTypeManager(config=topsdb_config)
    procedures = pmt.get_all_procedure_types_query().filter(
        and_(
            ProcedureType.short_label.startswith(procedure_type_prefix),
            ProcedureType.is_visible == True
        )
    )

    if not args.keep_procedures:
        logger.debug(f"Deleting all Existing External Procedures.")
        session.query(ExternalProcedure).delete()

    for procedure in procedures:
        if args.keep_procedures:
            existing_procedure = session.query(
                ExternalProcedure).filter_by(code=procedure.type_id).first()
            if existing_procedure:
                logger.debug(f"Modifying Existing Procedure {procedure.type_label}")
                existing_procedure.from_tops_procedure(procedure)
            else:
                ext = ExternalProcedure(tops_procedure=procedure)
                logger.debug(f"Adding New Procedure {procedure.type_label}")
                session.add(ext)
        else:
            ext = ExternalProcedure(tops_procedure=procedure)
            logger.debug(f"Adding New Procedure {procedure.type_label}")
            session.add(ext)


def import_terminology(session):
    """Import all codes from FHIR CodeSystems."""
    logger.debug("Importing Terminology from FHIR CodeSystems")
    
    for codesystem_url in CODESYSTEM_URLS:
        try:
            response = requests.get(codesystem_url)
            response.raise_for_status()
            
            codesystem = CodeSystem.model_validate(response.json())
            # Find the DICOM identifier
            dicom_id = next((identifier.value 
                           for identifier in (codesystem.identifier or [])
                           if identifier.system == "dicom"), 
                          None)
            
            for concept in codesystem.concept or []:
                scheduled_protocol = ScheduledProtocol()
                scheduled_protocol.from_concept(concept)
                if dicom_id:
                    scheduled_protocol.code_scheme = dicom_id
                session.add(scheduled_protocol)
                logger.debug(f"Added code {concept.display} with scheme {dicom_id}")
                    
        except Exception as e:
            logger.error(f"Error importing from {codesystem_url}: {str(e)}")

def main():
    args = ArgsCache.get_arguments()

    level = verbosity_mapping.get(args.verbose, logging.WARNING)
    logging.getLogger().setLevel(level)  # Set the root logger level
    logger.setLevel(level)
    logger.propagate = True
    logger.warning(f"effective level: {logger.getEffectiveLevel()}, LOG LEVEL: {level}, verbose: {args.verbose}")


    topsdb_config = {
        'username': args.topsserver_username,
        'password': args.topsserver_password,
        'host': args.topsserver_ip,
        'port': int(args.topsserver_port),
    }

    if not database_exists_and_valid():
        init_database()

    session = get_session()
    import_procedures(session,topsdb_config)
    import_terminology(session)
    session.commit()


def sigint_signal_handler(signal, frame):
    '''This will catch a SIGINT or ctrl-C and print what was done so far.'''
    sys.exit(0)


signal.signal(signal.SIGINT, sigint_signal_handler)


if __name__ == "__main__":
    sys.exit(main())
