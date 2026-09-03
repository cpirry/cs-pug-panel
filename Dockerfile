FROM docker:27-cli

RUN apk add --no-cache python3

WORKDIR /app
COPY app.py .
COPY core ./core
COPY static ./static

EXPOSE 8080
CMD ["python3", "app.py"]
