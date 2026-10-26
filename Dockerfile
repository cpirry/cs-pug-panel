FROM docker:27-cli

RUN apk add --no-cache python3

WORKDIR /app
COPY . .

EXPOSE 8080
CMD ["python3", "app.py"]
