FROM python:3.11-slim
WORKDIR /mma
COPY . /mma
RUN pip install --no-cache-dir .
CMD ["python", "run.py", "--help"]
