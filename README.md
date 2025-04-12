# URL Shortener Web Service 

A simple, robust, and scalable URL shortener web service built with Python, Flask, and Redis, including a basic web frontend.

## Description

This project provides a web service that takes a long URL as input and returns a shorter, unique URL. When a user accesses the short URL, they are redirected to the original long URL. This version uses **Redis** for persistent storage and includes a simple **HTML/JavaScript frontend** (served from `index.html`) for easy interaction.

## Features

* **Web Frontend:** Simple interface (served via `/`) to shorten URLs. Assumes an `index.html` file exists.
* **URL Shortening:** Generates a unique, short URL for any valid long URL via the `/shorten` API endpoint.
* **URL Redirection:** Redirects users from the short URL path (e.g., `/aBcDeF`) to the original long URL.
* **Persistent Storage:** Uses **Redis** to store URL mappings (`short_path -> url` and `url -> short_path`), ensuring data persists across server restarts.
* **Base62 Encoding:** Uses Base62 encoding for compact and URL-friendly short link paths.
* **Hashing & Collision Handling:** Employs SHA256 hashing and a simple retry mechanism to generate unique identifiers for URLs and handle potential (though rare) collisions.
* **Input Validation:** Ensures that provided URLs are valid (`http://` or `https://` required) before processing.
* **Error Handling:** Provides clear JSON error messages for API errors (4xx, 5xx) and basic HTML error pages for frontend/redirect errors.
* **Scalability:** Redis provides a scalable backend for handling many URLs.
* **Production Ready:** Includes considerations for production deployment (environment variables, WSGI server, Redis).

## Requirements

* Python 3.7+
* Flask
* Werkzeug (usually installed with Flask)
* **Redis Server:** A running Redis instance.
* **redis-py:** The Python client for Redis (`pip install redis`).
* An `index.html` file in the same directory as the Python script (for the frontend).
* (Optional for Production) A WSGI server like Gunicorn or uWSGI.

## Installation

1.  **`Clone the repository (or download the code usws.py and index.html):`**

2.  **Create and activate a virtual environment (recommended):**
    ```bash
    # In your project directory
    python3 -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3.  **Install the required Python packages:**
    ```bash
    # Make sure your virtual environment is active
    pip install Flask Werkzeug redis
    ```

4.  **Ensure Redis is running:** You need a Redis server accessible. You can run Redis locally (e.g., using Docker: `docker run -d -p 6379:6379 redis`) or use a cloud-based Redis service. See previous troubleshooting steps if you have issues.

5.  **`Place index.html:`** Make sure the `index.html` frontend file is in the same directory as your Python script (`usws.py`).

## Configuration

The application uses environment variables for configuration. You can set these directly in your shell, use a `.env` file (requires `python-dotenv` package), or configure them in your deployment environment:

* `SECRET_KEY`: A secret key used by Flask. Generate a strong random key for production.
    * Default: `'dev-secret-key-replace-in-prod'`
    * Example: `export SECRET_KEY='your_very_secret_random_string'`
* `BASE_URL`: The base URL where the application will be hosted (used to construct the full short URL).
    * Default: `'http://localhost:5000'`
    * Example: `export BASE_URL='https://your.short.domain'`
* `REDIS_URL`: The connection URL for your Redis instance.
    * Default: `'redis://localhost:6379/0'`
    * Example: `export REDIS_URL='redis://:yourpassword@your_redis_host:6379/0'`

## Running the Application

### Development

1.  **Ensure Redis is running and accessible** at the configured `REDIS_URL`.
2.  **Set environment variables (optional, defaults will be used otherwise):**
    ```bash
    # Example (optional)
    export BASE_URL='http://localhost:5000'
    export REDIS_URL='redis://localhost:6379/0'
    ```
3.  **Run the Flask application:**
    ```bash
    # Ensure usws.py and index.html are in the current directory
    # Make sure your virtual environment is active if you created one
    python usws.py # Or your Python script name
    ```
    *(The `if __name__ == "__main__":` block runs the app directly with debug mode enabled)*

    The application (including the frontend) will be available at `http://localhost:5000` by default. The script will print "Successfully connected to Redis." if the connection works, otherwise it will print an error and exit.

### Production

For production:

1.  **Ensure Redis is running** and configured correctly via the `REDIS_URL` environment variable.
2.  **Set Environment Variables:** Set `SECRET_KEY`, `BASE_URL`, and `REDIS_URL` appropriately for your production environment.
3.  **Use a production-grade WSGI server** like Gunicorn or uWSGI. Do **not** use the Flask development server (`app.run(debug=True)`).

**Example using Gunicorn:**

1.  Install Gunicorn in your virtual environment:
    ```bash
    pip install gunicorn
    ```
2.  Run the application (make sure your environment variables are set):
    ```bash
    # Example assumes your script is named usws.py and Flask app instance is 'app'
    gunicorn --workers 4 --bind 0.0.0.0:5000 usws:app
    # Adjust --workers based on your server's CPU cores
    ```
    It's highly recommended to run Gunicorn behind a reverse proxy like Nginx or Apache.

## Using the Frontend

1.  Navigate to the application's base URL (e.g., `http://localhost:5000`) in your web browser. This serves the `index.html` file.
2.  Enter a long URL (including `http://` or `https://`) into the input field.
3.  Click the "Shorten URL" button.
4.  The frontend will call the `/shorten` API endpoint.
5.  If successful, the shortened URL will appear. You can click the short URL to test the redirect or copy it.
6.  Errors (e.g., invalid URL format, server issues) will be displayed in an error box on the page.

## API Endpoints (For Programmatic Use)

### 1. Shorten URL

* **Method:** `POST`
* **Endpoint:** `/shorten`
* **Request Body (JSON):**
    ```json
    {
      "url": "[https://www.google.com/search?q=long+url+example](https://www.google.com/search?q=long+url+example)"
    }
    ```
* **Success Response (200 OK):**
    ```json
    {
      "short_url": "http://localhost:5000/generatedShortPath",
      "original_url": "[https://www.google.com/search?q=long+url+example](https://www.google.com/search?q=long+url+example)"
    }
    ```
* **Error Responses:**
    * `400 Bad Request`: Invalid JSON, missing `url`, or invalid URL format (`{"error": "..."}`).
    * `500 Internal Server Error`: Failure during short URL generation (e.g., collision issue) (`{"error": "..."}`).
    * `503 Service Unavailable`: Cannot connect to Redis (`{"error": "..."}`).

**`Example using curl:`**

```bash
curl -X POST -H "Content-Type: application/json" \
     -d '{"url": "[https://www.example.com/a/very/long/path/that/needs/shortening](https://www.example.com/a/very/long/path/that/needs/shortening)"}' \
     http://localhost:5000/shorten
```

### 2. Redirect to Original URL

* **Method:** `GET`
* **Endpoint:** `/<short_url_path>`
    * Example: `http://localhost:5000/aBcDeF`
* **Success Response:**
    * `302 Found` Redirect to the original long URL.
* **Error Response:**
    * `404 Not Found`: If the `short_url_path` does not exist in Redis (returns HTML error page by default).
    * `503 Service Unavailable`: Cannot connect to Redis (returns HTML error page).

## Technology Stack

* **Language:** Python 3
* **Backend Framework:** Flask
* **Database:** Redis
* **Frontend:** HTML, JavaScript (specific libraries depend on `index.html`), CSS (e.g., Tailwind via CDN in the provided example `index.html`)
* **WSGI Server (Production):** Gunicorn / uWSGI
