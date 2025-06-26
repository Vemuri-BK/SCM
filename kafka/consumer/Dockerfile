FROM python:3.9

# Set working directory
WORKDIR /app

# Copy consumer code
COPY consumer.py .

# Install dependencies
RUN pip install kafka-python pymongo

# Command to run the consumer
CMD ["python", "consumer.py"]
