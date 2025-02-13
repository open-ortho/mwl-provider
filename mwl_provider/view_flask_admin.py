from mwl_provider.model import (
    ExternalProcedure, RequestedProcedure, ScheduledProcedureStep, ScheduledProtocol, database_exists_and_valid, init_database
)
from mwl_provider import logger
from mwl_provider.utils import generate_new_flask_secret_key
from mwl_provider.args_cache import ArgsCache
from sqlalchemy import or_, not_
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_admin.contrib.sqla.view import func
from flask_admin.form.widgets import Select2Widget
from wtforms_sqlalchemy.fields import QuerySelectMultipleField, QuerySelectField

from mwl_provider.model import get_engine_url

args = ArgsCache.get_arguments()
flask_app = Flask(__name__)
flask_app.config['SQLALCHEMY_DATABASE_URI'] = get_engine_url()
flask_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
if not hasattr(args, "flask_secret_key") or not args.flask_secret_key:
    flask_secret_key = generate_new_flask_secret_key()
    logger.warning(
        f"Generated a New Flask Secret Key: [{str(flask_secret_key)}]")
else:
    flask_secret_key = args.flask_secret_key
flask_app.secret_key = flask_secret_key
db = SQLAlchemy(flask_app)


@flask_app.route('/')
def index():
    db_exists_and_valid = database_exists_and_valid()
    if not db_exists_and_valid:
        init_database()
    # This is a safe place to use db.engine.url
    logger.debug(f"Using DB {db.engine.url}.")
    return f"""
<h1>mwl-provider Configuration</h1>
<p>
Created New Database: {not db_exists_and_valid}</br>
Flask: {db.engine.url}</br>
Alchemy: {get_engine_url()}
</p>
    """


class CustomSelect2Widget(Select2Widget):
    def __call__(self, field, **kwargs):
        # Set default size attribute to a larger value or full available size
        kwargs.setdefault('size', '10')  # Increase size to show more rows
        kwargs['multiple'] = 'multiple'

        return super(CustomSelect2Widget, self).__call__(field, **kwargs)


class ExternalProcedureView(ModelView):
    form_columns = ['system', 'code', 'name',
                    'short_name', 'requested_procedure']
    column_list = ['code', 'name', 'short_name', 'requested_procedure_name']
    form_args = {
        'requested_procedure': {
            'query_factory': lambda: db.session.query(RequestedProcedure),
            'get_label': lambda req_proc: req_proc.name or '[Unnamed Requested Procedure]',
            'widget': CustomSelect2Widget()
        }
    }
    form_overrides = {
        'requested_procedure': QuerySelectField
    }

    def _requested_procedure_formatter(self, context, model, name):
        # Check if the requested_procedure relationship is populated
        if model.requested_procedure:
            return model.requested_procedure.name
        return "[UNASSIGNED]"

    column_formatters = {
        'requested_procedure_name': _requested_procedure_formatter
    }


class RequestedProcedureView(ModelView):
    form_columns = ['name', 'comments', 'description', 'code_value', 'code_scheme',
                    'code_meaning', 'requesting_physician_name', 'external_procedures', 'scheduled_procedure_steps']
    form_args = {
        'scheduled_procedure_steps': {
            'query_factory': lambda: db.session.query(ScheduledProcedureStep),
            # Provide a default label for None values
            'get_label': lambda step: step.name or '[Unnamed Scheduled Procedure Step]',
            'widget': CustomSelect2Widget()
        },
        'external_procedures': {
            'query_factory': lambda: db.session.query(ExternalProcedure),
            # Provide a default label for None values
            'get_label': lambda procedure: procedure.name or '[Unnamed External Procedure]',
            'widget': CustomSelect2Widget()
        }
    }
    form_overrides = {
        'scheduled_procedure_steps': QuerySelectMultipleField,
        'external_procedures': QuerySelectMultipleField
    }

    column_list = ('name', 'code_value', 'code_scheme',
                   'code_meaning', 'scheduled_procedure_steps_names')

    def scheduled_procedure_step_names(self, context, model, name):
        return ', '.join(procedure_step.name for procedure_step in model.scheduled_procedure_steps)

    column_formatters = {
        'scheduled_procedure_steps_names': scheduled_procedure_step_names
    }


class ScheduledProcedureStepView(ModelView):
    form_columns = ['name', 'modality', 'station_ae_title', 'code_value', 'code_scheme',
                    'code_meaning', 'performing_physicians_name', 'protocols', 'requested_procedures']
    form_args = {
        'protocols': {
            'query_factory': lambda: db.session.query(ScheduledProtocol).order_by(ScheduledProtocol.name),
            # Provide a default label for None values
            'get_label': lambda protocol: protocol.name or '[Unnamed Protocol]',
            'widget': CustomSelect2Widget()
        },
        'requested_procedures': {
            'query_factory': lambda: db.session.query(RequestedProcedure),
            # Provide a default label for None values
            'get_label': lambda procedure: procedure.name or '[Unnamed Requested Procedure]',
            'widget': CustomSelect2Widget()
        }

    }
    form_overrides = {
        'protocols': QuerySelectMultipleField,
        'requested_procedures': QuerySelectMultipleField
    }
    column_list = ('name', 'code_value', 'code_scheme', 'code_meaning',
                   'modality', 'station_ae_title', 'protocols_names')

    def protocol_names(self, context, model, name):
        # Join names of all related protocols into a single string, handle None values
        return ', '.join(protocol.name or '[Unnamed Protocol]' for protocol in model.protocols)

    column_formatters = {
        'protocols_names': protocol_names
    }


class ScheduledProtocolView(ModelView):
    form_columns = ['name', 'code_value',
                    'code_scheme', 'code_meaning', 'procedures']
    form_args = {
        'procedures': {
            'query_factory': lambda: db.session.query(ScheduledProcedureStep).order_by(ScheduledProcedureStep.name),
            # Provide a default label for None values
            'get_label': lambda step: step.name or '[Unnamed Scheduled Procedure Step]',
            'widget': CustomSelect2Widget()
        }
    }
    form_overrides = {
        'procedures': QuerySelectMultipleField
    }
    column_list = ('name', 'code_value', 'code_scheme',
                   'code_meaning', 'scheduled_procedure_steps_names')

    def scheduled_procedure_steps_names(self, context, model, name):
        # Join names of all related scheduled procedure steps into a single string, handle None values
        return ', '.join(step.name or '[Unnamed Scheduled Procedure Step]' for step in model.procedures)

    column_formatters = {
        'scheduled_procedure_steps_names': scheduled_procedure_steps_names
    }


# Initialize Flask-Admin
admin = Admin(flask_app, name='topsDicom Admin', template_mode='bootstrap3')

# Add views for each model
admin.add_view(ExternalProcedureView(ExternalProcedure, db.session))
admin.add_view(RequestedProcedureView(RequestedProcedure, db.session))
admin.add_view(ScheduledProcedureStepView(ScheduledProcedureStep, db.session))
admin.add_view(ScheduledProtocolView(ScheduledProtocol, db.session))
