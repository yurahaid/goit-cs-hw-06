# Use the latest Python version as the base image
FROM python:latest

# Set the working directory in the container
WORKDIR /app

COPY . .

# Install required Python packages
RUN pip install --no-cache-dir -r requirements.txt


# Specify the default command to run
ENTRYPOINT ["python", "main.py"]