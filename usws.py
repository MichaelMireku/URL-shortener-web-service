import hashlib
import base64
from flask import Flask, request, redirect, jsonify, abort, render_template_string # Added render_template_string
from urllib.parse import urlparse
import os
import redis # Added redis
from werkzeug.middleware.proxy_fix import ProxyFix

# Initialize Flask application
app = Flask(__name__)

# Apply ProxyFix - Useful when running behind a proxy server like Nginx or Heroku
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# --- Configuration ---
# Use environment variables for production, provide sensible defaults for development
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-replace-in-prod')
app.config['BASE_URL'] = os.environ.get('BASE_URL', 'http://localhost:5000')
# Default to a local Redis instance if REDIS_URL is not set
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

# --- Redis Connection ---
try:
    # Connect to Redis. decode_responses=True ensures keys/values are strings
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    redis_client.ping() # Check if the connection is successful
    print("Successfully connected to Redis.")
except redis.exceptions.ConnectionError as e:
    print(f"Error connecting to Redis: {e}")
    print("Please ensure Redis is running and accessible at the configured REDIS_URL.")
    # In a real app, you might exit or have a fallback, but for now, we'll print an error.
    # Exiting might be better in production if Redis is essential.
    # exit(1)
    redis_client = None # Set to None to handle gracefully later

# --- Helper Functions ---

def base62_encode(num, alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'):
    """Encode a positive integer into a Base62 string."""
    if num == 0:
        return alphabet[0]
    arr = []
    base = len(alphabet)
    while num:
        num, rem = divmod(num, base)
        arr.append(alphabet[rem])
    arr.reverse()
    return ''.join(arr)

def get_short_url(url):
    """
    Generates a short URL path for a given URL using Redis.

    Args:
        url (str): The URL to shorten.

    Returns:
        str: The short URL path (e.g., 'aBcDeF'). Returns None if Redis is unavailable.
    """
    if not redis_client:
        print("Redis client not available.")
        return None # Cannot proceed without Redis

    # 1. Check if the URL already exists (reverse lookup: url -> short_path)
    #    We store two mappings: short_path -> url and url -> short_path
    #    This makes lookups faster in both directions.
    existing_short_path = redis_client.get(f"url:{url}")
    if existing_short_path:
        print(f"URL '{url}' already exists with short path: {existing_short_path}")
        return existing_short_path

    # 2. Generate a unique hash and encode it
    #    Keep trying until we find a short_path that isn't already used.
    #    Collisions are rare but possible. Add a salt/counter if needed.
    max_attempts = 5 # Prevent infinite loops in extreme collision scenarios
    attempt = 0
    short_path = None
    while attempt < max_attempts:
        # Generate hash based on URL and attempt count (to ensure uniqueness on collision)
        hash_input = f"{url}:{attempt}".encode()
        url_hash = hashlib.sha256(hash_input).digest()
        truncated_hash_int = int.from_bytes(url_hash[:6], 'big') # Use 6 bytes for shorter URLs
        potential_short_path = base62_encode(truncated_hash_int)

        # 3. Check if this potential short path already exists in Redis
        #    Use SETNX (SET if Not eXists) for an atomic check-and-set operation.
        #    We temporarily set the short_path -> url mapping. If successful (NX), it's unique.
        if redis_client.setnx(f"short:{potential_short_path}", url):
            short_path = potential_short_path
            break # Found a unique path

        print(f"Collision detected for short path: {potential_short_path}. Retrying...")
        attempt += 1

    if not short_path:
        print(f"Failed to generate a unique short URL for '{url}' after {max_attempts} attempts.")
        # Handle failure - maybe log, alert, or return an error
        return None # Indicate failure

    # 4. Store the reverse mapping (url -> short_path) as well
    redis_client.set(f"url:{url}", short_path)
    print(f"Stored mapping: {short_path} -> {url}")

    return short_path

def is_valid_url(url):
    """Checks if a URL is valid."""
    try:
        result = urlparse(url)
        # Require scheme (http/https) and netloc (domain name)
        return all([result.scheme in ['http', 'https'], result.netloc])
    except ValueError:
        return False

# --- API Endpoints ---

@app.route('/shorten', methods=['POST'])
def shorten_url_api():
    """API endpoint to shorten a URL."""
    if not redis_client:
        return jsonify({'error': 'Service Unavailable: Database connection failed'}), 503

    # 1. Get URL from JSON payload
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({'error': 'URL is required in JSON payload'}), 400

    long_url = data['url']

    # 2. Validate the URL
    if not is_valid_url(long_url):
        return jsonify({'error': 'Invalid URL provided. Ensure it includes http:// or https://'}), 400

    # 3. Generate the short URL path
    short_url_path = get_short_url(long_url)
    if not short_url_path:
         # Handle case where short URL generation failed (e.g., too many collisions)
        return jsonify({'error': 'Failed to generate short URL. Please try again.'}), 500

    # 4. Construct the full short URL
    short_url = f"{app.config['BASE_URL']}/{short_url_path}"

    # 5. Return the result
    return jsonify({'short_url': short_url, 'original_url': long_url}), 200

@app.route('/<short_url_path>')
def redirect_to_original_url(short_url_path):
    """Redirects a short URL path to its original URL."""
    if not redis_client:
        # If Redis is down, we can't perform lookups
        # Render a simple error page instead of JSON
        return render_template_string("""
            <!DOCTYPE html><html><head><title>Error</title></head>
            <body><h1>Service Unavailable</h1><p>Could not connect to the database.</p></body></html>
        """), 503

    # 1. Look up the original URL in Redis using the short path
    original_url = redis_client.get(f"short:{short_url_path}")

    if original_url:
        # 2. Redirect if found
        print(f"Redirecting '{short_url_path}' to '{original_url}'")
        # Consider adding click tracking here (e.g., increment a counter in Redis)
        # redis_client.incr(f"clicks:{short_url_path}")
        return redirect(original_url, code=302) # Use 302 for temporary redirect
    else:
        # 3. Return 404 if not found
        print(f"Short URL path not found: '{short_url_path}'")
        abort(404)

# --- Frontend Endpoint ---
@app.route('/', methods=['GET'])
def index():
    """Serves the basic HTML frontend."""
    # This HTML is now moved to a separate file for clarity
    # You would typically use Flask's render_template() with Jinja2 templates
    # For simplicity here, we keep it basic.
    # In a real app: return render_template('index.html')
    # Serve the index.html file (created in the next step)
    # For this example, we assume index.html is in the same directory
    try:
        # Best practice: Use render_template('index.html') if using Flask templates folder
        # For self-contained example, read the file directly (less common in Flask)
        # return app.send_static_file('index.html') # If index.html is in a 'static' folder
        with open('index.html', 'r') as f:
             return f.read()
    except FileNotFoundError:
        return "Error: index.html not found.", 404


# --- Error Handlers ---
@app.errorhandler(404)
def not_found(error):
    """Custom 404 error handler."""
    # Check if the request expects JSON or HTML
    if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
        return jsonify({'error': 'Not Found', 'message': 'The requested resource was not found.'}), 404
    else:
        # You could render a nice HTML 404 page here
        return render_template_string("""
            <!DOCTYPE html><html><head><title>404 Not Found</title></head>
            <body><h1>404 - Not Found</h1><p>The link you followed may be broken, or the page may have been removed.</p>
            <p><a href="/">Back to Home</a></p></body></html>
        """), 404

@app.errorhandler(500)
def internal_error(error):
    """Custom 500 error handler."""
    # Log the error details here in a real application
    print(f"Server Error: {error}")
    if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
        return jsonify({'error': 'Internal Server Error', 'message': 'Something went wrong on our end.'}), 500
    else:
        return render_template_string("""
            <!DOCTYPE html><html><head><title>500 Internal Server Error</title></head>
            <body><h1>500 - Internal Server Error</h1><p>Sorry, something went wrong on our server. Please try again later.</p></body></html>
        """), 500


# --- Main Execution ---
if __name__ == "__main__":
    # Ensure Redis is available before starting
    if not redis_client:
        print("Exiting: Redis connection failed.")
        exit(1) # Exit if Redis isn't working on startup

    # Run with debug=True for development ONLY
    # Use a proper WSGI server (Gunicorn/uWSGI) in production
    app.run(debug=True, threaded=True, host='0.0.0.0', port=5000)
