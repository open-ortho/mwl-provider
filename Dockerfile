# Use a lightweight Python image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy only the wheel file
COPY dist/*.whl /app/

# Install system dependencies and wheel
RUN pip install --no-cache-dir *.whl

# Create required directories
RUN mkdir -p /var/lib/tops-dicom/

# Copy configuration files
COPY alembic.ini /app/alembic.ini
COPY alembic /app/alembic

# Environment configuration
ENV TD_DICOM_SCP=True
ENV TD_CONFIGURATOR_UI=True

# Run the application
CMD ["python", "-m", "mwl_provider"]
