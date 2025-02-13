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

_

## MWL

mwl-provider will only return modality worklists if:

- the Modality requested matches one in the ScheduledProcedureStep requested.
- There must be an association between the ExternalProcedure and a RequestedProcedure in the local DB.

## Terms and Codes

mwl-provider works terminology servers.

- you need to generate DICOM Modality Worklists using different codes,
- the DICOM images are coded using a different coding scheme from the one in topsdb
- you need to export DICOM images using a different coding scheme

then you will need to configure the `TD_TERMINOLOGY_SERVER_URL`. 
