# 1. Use the official, lightweight Python image
FROM python:3.10-slim

# 2. Tell Docker to do all following work in an /app directory
WORKDIR /app

# 3. Copy your requirements file and install the dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy the rest of your Python code into the container
COPY . .

# 5. Expose the port FastAPI runs on
EXPOSE 8001

# 6. The command to start your application
# (Change "main:app" if your main python file is named something else, like "app.py")
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8001"]