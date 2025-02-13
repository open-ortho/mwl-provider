# mwl-provider

A DICOM Modality Worklist Provider from FHIR.

Looks up Encounters from a MWL and serves DICOM Modality Worklist. Mapping between Encounter procedures and Requeste Proceudure, Scheduled Protocol Codes

mwl-provider serves the following purposes and functionalities:

1. Generate and serve DICOM Modality Worklists.
2. Responds to DICOM C-FIND queries.

- [IHE RAD-5 Test](https://gazelle.ihe.net/GMM/test.seam?id=12600)

## Installing

To install, use docker. See `docker-compose.yml` for example.

## First Time Usage

1. You can start with the local docker compose, which should start up a working environment with mwl-provider serving a mock topsserver.
2. Look at the `docker-compose.yml` for usage examples. Keep in mind that the entrypoints don't take any CLI arguments. Only ENV vars.
3. DB is intialized only when you access `/`, for example [http://localhost:5001/](http://localhost:5001/).
4. Access `/admin` page. For example [http://localhost:5001/admin/](http://localhost:5001/admin/).

### Import appointment types from topsdb: `topsdcmimport`

The `topsdcmimport` tool will import any appointment procedures from the topsdb which start with the prefix defined in `mwl_provider.MWL_PREFIX`. This can be overridde with the environment variable `TD_PROCEDURE_TYPE_PREFIX`.


## MWL

mwl-provider will only return modality worklists if:

- the Modality requested matches one in the ScheduledProcedureStep requested.
- The topsdb appointment object has a non-null checked_in_time
- The topsdb appointment's procedure_type of the requested date has a corresponding External Procedure Code
- There must be an association between the ExternalProcedure and a RequestedProcedure in the local DB.

## Terms and Codes

mwl-provider works with topsOrtho, and understands only the codes and terms as defined in the *_types tables of the `topsdb`. If 

- you need to generate DICOM Modality Worklists using different codes,
- the DICOM images are coded using a different coding scheme from the one in topsdb
- you need to export DICOM images using a different coding scheme

then you will need to configure the `TD_TERMINOLOGY_SERVER_URL`. 

Keep in mind that `tops-fhir` provides its CodeSystems with a system URL that is DB dependent, meaning it contains the database UUID in the URL itself, like `http://topsortho.com/fhir/practice/<UUID>/CodeSystem/image-label-types`. `mwl-provider` will use the UUID of the current tops server for that. This is to allow for the same terminology server to include CodeSystems from multiple different topsServers, and not get confused.

