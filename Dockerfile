FROM python:3.10-slim

WORKDIR /app

# Install system dependencies required for OpenCV and other libraries
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Set environment variables
ENV PYTHONPATH=/app
ENV FLASK_APP=src/web/dataset_tool.py

# Expose the port the app runs on
EXPOSE 5001

# Command to run the application
CMD ["python3", "src/web/dataset_tool.py"]
