import requests
from flask import Flask, request, render_template, g, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from bs4 import BeautifulSoup

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Add a secret key for session management
DATABASE = 'database.db'
OMDB_API_KEY = 'e45abe68'  # Your OMDb API key

# Function to get a database connection
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row  # Return rows as dictionaries for easier access
    return db

# Close the database connection at the end of each request
@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.before_request
def require_login():
    allowed_routes = ['login', 'register']
    if request.endpoint not in allowed_routes and 'user_id' not in session:
        return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password)

        db = get_db()
        cur = db.cursor()
        try:
            cur.execute('INSERT INTO User (username, password) VALUES (?, ?)', (username, hashed_password))
            db.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already exists!', 'danger')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        db = get_db()
        cur = db.cursor()
        cur.execute('SELECT id, password FROM User WHERE username = ?', (username,))
        user = cur.fetchone()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        flash('Invalid credentials!', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Logged out successfully!', 'success')
    return redirect(url_for('login'))

@app.route('/fetch_movie', methods=['GET', 'POST'])
def fetch_movie():
    user_id = session['user_id']
    if request.method == 'POST':
        title = request.form['title']
        release_year = request.form['release_year']
        user_rating = request.form.get('user_rating', type=float)

        # Fetch movie data from OMDb API
        omdb_url = f'http://www.omdbapi.com/?t={title}&y={release_year}&apikey={OMDB_API_KEY}'
        response = requests.get(omdb_url)
        movie_data = response.json()

        if movie_data.get('Response') == 'True':
            db = get_db()
            cur = db.cursor()

            # Insert movie data, including user rating and user_id
            cur.execute('''
                INSERT INTO Movie (title, release_year, genre, rated, released, runtime, plot, language, country,
                                   awards, poster, imdbRating, imdbVotes, imdbID, type, totalSeasons, user_rating, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                movie_data.get('Title'), movie_data.get('Year'), movie_data.get('Genre'), movie_data.get('Rated'),
                movie_data.get('Released'), movie_data.get('Runtime'), movie_data.get('Plot'),
                movie_data.get('Language'), movie_data.get('Country'), movie_data.get('Awards'),
                movie_data.get('Poster'), movie_data.get('imdbRating'), movie_data.get('imdbVotes'),
                movie_data.get('imdbID'), movie_data.get('Type'), movie_data.get('totalSeasons'), user_rating, user_id
            ))
            movie_id = cur.lastrowid  # Get the ID of the inserted movie

            # Process directors, writers, and actors
            for role, names in [
                ('Director', movie_data.get('Director', '')),
                ('Writer', movie_data.get('Writer', '')),
                ('Actor', movie_data.get('Actors', ''))
            ]:
                for name in names.split(', '):
                    if name:
                        person_id = add_person_if_not_exists(db, name, user_id)
                        if role == 'Actor':
                            cur.execute('INSERT INTO MovieActor (movie_id, person_id, role) VALUES (?, ?, ?)', (movie_id, person_id, "Actor"))
                        elif role == 'Director':
                            cur.execute('INSERT INTO MovieDirector (movie_id, person_id) VALUES (?, ?)', (movie_id, person_id))
                        elif role == 'Writer':
                            cur.execute('INSERT INTO MovieWriter (movie_id, person_id) VALUES (?, ?)', (movie_id, person_id))

            db.commit()
            return redirect(url_for('index'))
        else:
            return f"Movie not found: {movie_data.get('Error')}", 404

    return render_template('fetch_movie.html')

@app.route('/')
def index():
    user_id = session['user_id']
    sort_by = request.args.get('sort_by', 'title')
    order = request.args.get('order', 'asc')
    new_order = 'desc' if order == 'asc' else 'asc'

    db = get_db()
    cur = db.cursor()

    query = f'''
        SELECT 
            Movie.id, 
            Movie.title, 
            Movie.release_year, 
            Movie.genre, 
            Movie.rated, 
            Movie.imdbRating,
            Movie.country,
            Movie.user_rating,
            GROUP_CONCAT(DISTINCT PersonDirector.name) AS director,
            GROUP_CONCAT(DISTINCT PersonWriter.name) AS writer,
            GROUP_CONCAT(DISTINCT PersonActor.name) AS actors
        FROM Movie
        LEFT JOIN MovieDirector ON Movie.id = MovieDirector.movie_id
        LEFT JOIN Person AS PersonDirector ON MovieDirector.person_id = PersonDirector.id
        LEFT JOIN MovieWriter ON Movie.id = MovieWriter.movie_id
        LEFT JOIN Person AS PersonWriter ON MovieWriter.person_id = PersonWriter.id
        LEFT JOIN MovieActor ON Movie.id = MovieActor.movie_id
        LEFT JOIN Person AS PersonActor ON MovieActor.person_id = PersonActor.id
        WHERE Movie.user_id = ?
        GROUP BY Movie.id
        ORDER BY {sort_by} {order}
    '''
    cur.execute(query, (user_id,))
    movies = cur.fetchall()

    return render_template('index.html', movies=movies, sort_by=sort_by, order=order, new_order=new_order)

@app.route('/movie/<int:movie_id>')
def movie_detail(movie_id):
    user_id = session['user_id']
    db = get_db()
    cur = db.cursor()

    # Fetch movie details
    cur.execute('''
        SELECT title, release_year, genre, rated, released, runtime, plot, language, country, awards, poster, imdbRating, imdbVotes, imdbID, type, totalSeasons
        FROM Movie WHERE id = ? AND user_id = ?
    ''', (movie_id, user_id))
    movie = cur.fetchone()

    # Fetch average rating
    cur.execute('SELECT average_rating FROM MovieRating WHERE movie_id = ?', (movie_id,))
    average_rating = cur.fetchone()

    return render_template('movie_detail.html', movie=movie, average_rating=average_rating)

def add_person_if_not_exists(db, name, user_id):
    cur = db.cursor()
    cur.execute('SELECT id FROM Person WHERE name = ? AND user_id = ?', (name, user_id))
    person = cur.fetchone()

    if person:
        return person['id']

    cur.execute('INSERT INTO Person (name, user_id) VALUES (?, ?)', (name, user_id))
    db.commit()
    return cur.lastrowid

def fetch_wikipedia_summary(name):
    """
    Fetch biographical data from Wikipedia.
    Returns: bio, image_url, birthday, birthplace
    """
    try:
        # Format the name for the Wikipedia URL
        formatted_name = name.replace(' ', '_')
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{formatted_name}"
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            bio = data.get('extract', '')
            image_url = data.get('thumbnail', {}).get('source', '')
            
            # Initialize birthday and birthplace as None
            birthday = None
            birthplace = None
            
            return bio, image_url, birthday, birthplace
        else:
            return None, None, None, None
            
    except Exception as e:
        print(f"Error fetching Wikipedia data: {e}")
        return None, None, None, None

if __name__ == '__main__':
    app.run(debug=True)