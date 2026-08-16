FROM python:3.11-slim

WORKDIR /app

# Install uv for dependency management
RUN pip install uv

# Copy project files
COPY pyproject.toml .

# Install dependencies using uv
RUN uv pip install --system -e .

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
