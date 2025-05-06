# Get base image
FROM gcr.io/google.com/cloudsdktool/cloud-sdk:latest 

# Install python3-venv
RUN apt-get update && \
    apt-get install -y python3-venv && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set up envrionment variables
ENV VENV_PATH=/venv
ENV PATH="${VENV_PATH}/bin:$PATH"

# Set up working directory
WORKDIR /api_key_rotation

# Create a virtual env
RUN python3 -m venv ${VENV_PATH}

# Install boto3
RUN ${VENV_PATH}/bin/pip install --upgrade pip boto3

# Copy script into image
COPY api_key_rotation.py ./

# Set entrypoint to run script
ENTRYPOINT ["python3", "api_key_rotation.py"]

# Default command
CMD ["-h"]
