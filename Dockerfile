FROM python:3.6.7-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY minimal_example.py .
CMD ["pytest", "minimal_example.py"]
