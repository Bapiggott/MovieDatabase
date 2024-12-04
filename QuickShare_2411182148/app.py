import requests
from flask import Flask, request, render_template, request, g, redirect, url_for, session, flash, jsonify
import sqlite3
import re
from datetime import datetime
from test import fetch_wikipedia_summary
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.secret_key = 'your_secret_key'
DATABASE = 'database.db'
OMDB_API_KEY = 'e45abe68'  # Your OMDb API key


# Function to get a database connection
def get_db():
    print("Getting database connection")
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row # Return rows as dictionaries for easier access
    return db


# Close the database connection at the end of each request
@app.teardown_appcontext
def close_connection(exception):
    print("Closing connection")
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()
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
            # Automatically log in the user after registration
            cur.execute('SELECT id FROM User WHERE username = ?', (username,))
            user = cur.fetchone()
            session['user_id'] = user['id']
            
            flash('Registration successful! Logged in automatically.', 'success')
            return redirect(url_for('index'))
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
            return redirect(url_for('index'))  # Redirect to homepage
        flash('Invalid credentials!', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Logged out successfully!', 'success')
    return redirect(url_for('login'))


@app.before_request
def require_login():
    allowed_routes = ['login', 'register']
    if request.endpoint not in allowed_routes and 'user_id' not in session:
        return redirect(url_for('login'))

@app.route('/fetch_movie', methods=['GET', 'POST'])
def fetch_movie():
    print("Fetching movie")
    if request.method == 'POST':
        print("POST request")
        title = request.form['title']
        release_year = request.form['release_year']
        user_rating = request.form.get('user_rating', type=float)  # Retrieve user rating

        # Fetch movie data from OMDb API
        omdb_url = f'http://www.omdbapi.com/?t={title}&y={release_year}&plot=full&apikey={OMDB_API_KEY}'
        response = requests.get(omdb_url)
        movie_data = response.json()
        if movie_data.get('Response') == 'True':
            return render_template('confirm_movie.html', movie=movie_data)
        else:
            flash("Movie not found. Please try again.", "danger")
            return redirect(url_for('fetch_movie'))

        if movie_data.get('Response') == 'True':
            db = get_db()
            cur = db.cursor()
            
            # Get the logged-in user's ID
            user_id = session['user_id']
            imdb_id = movie_data.get('imdbID')
            print(imdb_id)

            # Check if the movie already exists for this user
            cur.execute('SELECT 1 FROM Movie WHERE imdbID = ? AND user_id = ?', (imdb_id, user_id))
            existing_movie = cur.fetchone()
            print(f"existing_movie", existing_movie)
            if existing_movie != None:
                # Movie already exists for this user
                flash("This movie is already in your collection!", "warning")
                return redirect(url_for('index'))
                
            # Insert movie data, including user rating, and associate it with the current user
            cur.execute('''
                INSERT INTO Movie (title, release_year, genre, rated, released, runtime, plot, language, country,
                                   awards, poster, imdbRating, imdbVotes, imdbID, type, totalSeasons, user_rating, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                movie_data.get('Title'), movie_data.get('Year'), movie_data.get('Genre'), movie_data.get('Rated'),
                movie_data.get('Released'), movie_data.get('Runtime'), movie_data.get('Plot'),
                movie_data.get('Language'), movie_data.get('Country'), movie_data.get('Awards'),
                movie_data.get('Poster'), movie_data.get('imdbRating'), movie_data.get('imdbVotes'),
                imdb_id, movie_data.get('Type'), movie_data.get('totalSeasons'), user_rating, user_id
            ))
            movie_id = cur.lastrowid  # Get the ID of the inserted movie

            # Process directors
            for director_name in movie_data.get('Director', '').split(', '):
                if director_name:
                    director_id = add_person_if_not_exists(db, director_name)  # Pass user_id
                    cur.execute('INSERT INTO MovieDirector (movie_id, person_id) VALUES (?, ?)', (movie_id, director_id))

            # Process writers
            for writer_name in movie_data.get('Writer', '').split(', '):
                if writer_name:
                    writer_id = add_person_if_not_exists(db, writer_name)  # Pass user_id
                    cur.execute('INSERT INTO MovieWriter (movie_id, person_id) VALUES (?, ?)', (movie_id, writer_id))

            # Process actors
            for actor_name in movie_data.get('Actors', '').split(', '):
                if actor_name:
                    actor_id = add_person_if_not_exists(db, actor_name)  # Pass user_id
                    cur.execute('INSERT INTO MovieActor (movie_id, person_id, role) VALUES (?, ?, ?)', (movie_id, actor_id, "Actor"))

            db.commit()
            return redirect(url_for('index'))
        else:
            return f"Movie not found: {movie_data.get('Error')}", 404

    return render_template('fetch_movie.html')


@app.route('/confirm_movie', methods=['POST'])
def confirm_movie():
    if request.form.get('confirm') == 'Yes':
        title = request.form['title']
        release_year = request.form['year']
        user_rating = request.form.get('user_rating', type=float)  # Retrieve user rating

        # Fetch movie data from OMDb API
        omdb_url = f'http://www.omdbapi.com/?t={title}&y={release_year}&plot=full&apikey={OMDB_API_KEY}'
        response = requests.get(omdb_url)
        movie_data = response.json()
        if movie_data.get('Response') == 'True':
            db = get_db()
            cur = db.cursor()
            
            # Get the logged-in user's ID
            user_id = session['user_id']
            imdb_id = movie_data.get('imdbID')
            print(imdb_id)

            # Check if the movie already exists for this user
            cur.execute('SELECT 1 FROM Movie WHERE imdbID = ? AND user_id = ?', (imdb_id, user_id))
            existing_movie = cur.fetchone()
            print(f"existing_movie", existing_movie)
            if existing_movie != None:
                # Movie already exists for this user
                flash("This movie is already in your collection!", "warning")
                return redirect(url_for('index'))
                
            # Insert movie data, including user rating, and associate it with the current user
            cur.execute('''
                INSERT INTO Movie (title, release_year, genre, rated, released, runtime, plot, language, country,
                                   awards, poster, imdbRating, imdbVotes, imdbID, type, totalSeasons, user_rating, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                movie_data.get('Title'), movie_data.get('Year'), movie_data.get('Genre'), movie_data.get('Rated'),
                movie_data.get('Released'), movie_data.get('Runtime'), movie_data.get('Plot'),
                movie_data.get('Language'), movie_data.get('Country'), movie_data.get('Awards'),
                movie_data.get('Poster'), movie_data.get('imdbRating'), movie_data.get('imdbVotes'),
                imdb_id, movie_data.get('Type'), movie_data.get('totalSeasons'), user_rating, user_id
            ))
            movie_id = cur.lastrowid  # Get the ID of the inserted movie

            # Process directors
            for director_name in movie_data.get('Director', '').split(', '):
                if director_name:
                    director_id = add_person_if_not_exists(db, director_name)  # Pass user_id
                    cur.execute('INSERT INTO MovieDirector (movie_id, person_id) VALUES (?, ?)', (movie_id, director_id))

            # Process writers
            for writer_name in movie_data.get('Writer', '').split(', '):
                if writer_name:
                    writer_id = add_person_if_not_exists(db, writer_name)  # Pass user_id
                    cur.execute('INSERT INTO MovieWriter (movie_id, person_id) VALUES (?, ?)', (movie_id, writer_id))

            # Process actors
            for actor_name in movie_data.get('Actors', '').split(', '):
                if actor_name:
                    actor_id = add_person_if_not_exists(db, actor_name)  # Pass user_id
                    cur.execute('INSERT INTO MovieActor (movie_id, person_id, role) VALUES (?, ?, ?)', (movie_id, actor_id, "Actor"))

            db.commit()
            return redirect(url_for('index'))
    else:
        return f"Movie not found", 404



@app.route('/update_movies', methods=['POST'])
#@app.route('/update_rating/<int:movie_id>', methods=['POST'])
def update_movies():
    print("Updating movies")
    user_rating = request.form.get('user_rating', type=float)
    print(user_rating)
    db = get_db()
    cur = db.cursor()
    
    # Retrieve the logged-in user's ID
    user_id = session['user_id']
    
    # Fetch all movies for the logged-in user from the database
    cur.execute('SELECT id, title, release_year FROM Movie WHERE user_id = ?', (user_id,))
    movies = cur.fetchall()

    # Loop through each movie and update its data
    for movie in movies:
        movie_id, title, release_year = movie

        # Fetch updated data from OMDb API
        omdb_url = f'http://www.omdbapi.com/?t={title}&y={release_year}&plot=full&apikey={OMDB_API_KEY}'
        response = requests.get(omdb_url)
        movie_data = response.json()

        if movie_data.get('Response') == 'True':
            # Update movie data in the database
            cur.execute('''
                UPDATE Movie
                SET genre = ?, rated = ?, released = ?, runtime = ?, plot = ?, language = ?, country = ?,
                    awards = ?, poster = ?, imdbRating = ?, imdbVotes = ?, imdbID = ?, type = ?, totalSeasons = ?
                WHERE id = ? AND user_id = ?
            ''', (
                movie_data.get('Genre'), movie_data.get('Rated'), movie_data.get('Released'), movie_data.get('Runtime'),
                movie_data.get('Plot'), movie_data.get('Language'), movie_data.get('Country'), movie_data.get('Awards'),
                movie_data.get('Poster'), movie_data.get('imdbRating'), movie_data.get('imdbVotes'), movie_data.get('imdbID'),
                movie_data.get('Type'), movie_data.get('totalSeasons'), movie_id, user_id
            ))

            # Clear existing associations for directors, writers, and actors
            cur.execute('DELETE FROM MovieDirector WHERE movie_id = ?', (movie_id,))
            cur.execute('DELETE FROM MovieWriter WHERE movie_id = ?', (movie_id,))
            cur.execute('DELETE FROM MovieActor WHERE movie_id = ?', (movie_id,))

            # Update directors
            for director_name in movie_data.get('Director', '').split(', '):
                if director_name:
                    director_id = add_person_if_not_exists(db, director_name, user_id)  # Pass user_id
                    cur.execute('INSERT INTO MovieDirector (movie_id, person_id) VALUES (?, ?)', (movie_id, director_id))

            # Update writers
            for writer_name in movie_data.get('Writer', '').split(', '):
                if writer_name:
                    writer_id = add_person_if_not_exists(db, writer_name, user_id)  # Pass user_id
                    cur.execute('INSERT INTO MovieWriter (movie_id, person_id) VALUES (?, ?)', (movie_id, writer_id))

            # Update actors
            for actor_name in movie_data.get('Actors', '').split(', '):
                if actor_name:
                    actor_id = add_person_if_not_exists(db, actor_name, user_id)  # Pass user_id
                    cur.execute('INSERT INTO MovieActor (movie_id, person_id, role) VALUES (?, ?, ?)', (movie_id, actor_id, "Actor"))

    # Commit all updates to the database
    db.commit()
    return "Movies and associated people updated successfully!"




@app.route('/update_individual_movie/<int:movie_id>', methods=['GET'])
def update_individual_movie(movie_id):
    print("Updating individual movie")
    db = get_db()
    cur = db.cursor()
    
    # Fetch the specific movie from the database based on movie_id
    cur.execute('SELECT id, title, release_year FROM Movie WHERE id = ?', (movie_id,))
    movie = cur.fetchone()  # fetchone() retrieves a single row without needing an argument

    if movie is None:
        return "Movie not found", 404

    movie_id, title, release_year = movie

    # Fetch updated data from OMDb API
    omdb_url = f'http://www.omdbapi.com/?t={title}&y={release_year}&plot=full&apikey={OMDB_API_KEY}'
    response = requests.get(omdb_url)
    movie_data = response.json()

    if movie_data.get('Response') == 'True':
        # Update movie data in the database
        cur.execute('''
            UPDATE Movie
            SET genre = ?, rated = ?, released = ?, runtime = ?, plot = ?, language = ?, country = ?,
                awards = ?, poster = ?, imdbRating = ?, imdbVotes = ?, imdbID = ?, type = ?, totalSeasons = ?
            WHERE id = ?
        ''', (
            movie_data.get('Genre'), movie_data.get('Rated'), movie_data.get('Released'), movie_data.get('Runtime'),
            movie_data.get('Plot'), movie_data.get('Language'), movie_data.get('Country'), movie_data.get('Awards'),
            movie_data.get('Poster'), movie_data.get('imdbRating'), movie_data.get('imdbVotes'), movie_data.get('imdbID'),
            movie_data.get('Type'), movie_data.get('totalSeasons'), movie_id
        ))

        # Clear existing associations for directors, writers, and actors
        cur.execute('DELETE FROM MovieDirector WHERE movie_id = ?', (movie_id,))
        cur.execute('DELETE FROM MovieWriter WHERE movie_id = ?', (movie_id,))
        cur.execute('DELETE FROM MovieActor WHERE movie_id = ?', (movie_id,))

        # Update directors
        for director_name in movie_data.get('Director', '').split(', '):
            if director_name:
                director_id = add_person_if_not_exists(db, director_name)
                cur.execute('INSERT INTO MovieDirector (movie_id, person_id) VALUES (?, ?)', (movie_id, director_id))

        # Update writers
        for writer_name in movie_data.get('Writer', '').split(', '):
            if writer_name:
                writer_id = add_person_if_not_exists(db, writer_name)
                cur.execute('INSERT INTO MovieWriter (movie_id, person_id) VALUES (?, ?)', (movie_id, writer_id))

        # Update actors
        for actor_name in movie_data.get('Actors', '').split(', '):
            if actor_name:
                actor_id = add_person_if_not_exists(db, actor_name)
                cur.execute('INSERT INTO MovieActor (movie_id, person_id, role) VALUES (?, ?, ?)', (movie_id, actor_id, "Actor"))

    # Commit all updates to the database
    db.commit()
    return "Movie and associated people updated successfully!"

@app.route('/')
def index():
    sort_by = request.args.get('sort_by', 'title')  # Default to 'title'
    order = request.args.get('order', 'asc')  # Default order is ascending
    genre_filter = request.args.get('genre')  # Get the genre filter from query parameters
    country_filter = request.args.get('country')  # Get the country filter from query parameters
    new_order = 'desc' if order == 'asc' else 'asc'

    # Ensure sort_by is one of the allowed fields to prevent SQL injection
    allowed_fields = ['title', 'release_year', 'genre', 'rated', 'imdbRating', 'country', 'user_rating', 'average_rating']
    sort_by = sort_by if sort_by in allowed_fields else 'title'
    order = order if order in ['asc', 'desc'] else 'asc'

    db = get_db()
    cur = db.cursor()

    # Get the logged-in user's ID
    user_id = session['user_id']

    cur.execute('SELECT username FROM User WHERE id = ?', (user_id,))
    username = cur.fetchone()['username']


    # Update average ratings before fetching movies
    update_all_average_ratings()

    

    # Build query based on whether sorting by release_year or another field
    """if sort_by == 'release_year':
        query = f'''
            SELECT 
                Movie.id, 
                Movie.title, 
                SUBSTR(Movie.release_year, 1, 4) AS release_year, 
                Movie.genre, 
                Movie.rated, 
                Movie.imdbRating,
                Movie.country,
                Movie.user_rating,
                Movie.Poster,
                (SELECT average_rating FROM MovieRating WHERE MovieRating.movie_id = Movie.id) AS average_rating,
                GROUP_CONCAT(DISTINCT PersonDirector.id || ':' || PersonDirector.name) AS director,
                GROUP_CONCAT(DISTINCT PersonWriter.id || ':' || PersonWriter.name) AS writer,
                GROUP_CONCAT(DISTINCT PersonActor.id || ':' || PersonActor.name) AS actors
            FROM Movie
            LEFT JOIN MovieDirector ON Movie.id = MovieDirector.movie_id
            LEFT JOIN Person AS PersonDirector ON MovieDirector.person_id = PersonDirector.id
            LEFT JOIN MovieWriter ON Movie.id = MovieWriter.movie_id
            LEFT JOIN Person AS PersonWriter ON MovieWriter.person_id = PersonWriter.id
            LEFT JOIN MovieActor ON Movie.id = MovieActor.movie_id
            LEFT JOIN Person AS PersonActor ON MovieActor.person_id = PersonActor.id
            WHERE Movie.user_id = ?
            GROUP BY Movie.id
            ORDER BY SUBSTR(Movie.release_year, 1, 4) {order}
        '''
    else:"""
    r = True
    if r:
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
                Movie.Poster,
                (SELECT average_rating FROM MovieRating WHERE MovieRating.imdbID = Movie.imdbID) AS average_rating,
                GROUP_CONCAT(DISTINCT PersonDirector.id || ':' || PersonDirector.name) AS director,
                GROUP_CONCAT(DISTINCT PersonWriter.id || ':' || PersonWriter.name) AS writer,
                GROUP_CONCAT(DISTINCT PersonActor.id || ':' || PersonActor.name) AS actors
            FROM Movie
            LEFT JOIN MovieDirector ON Movie.id = MovieDirector.movie_id
            LEFT JOIN Person AS PersonDirector ON MovieDirector.person_id = PersonDirector.id
            LEFT JOIN MovieWriter ON Movie.id = MovieWriter.movie_id
            LEFT JOIN Person AS PersonWriter ON MovieWriter.person_id = PersonWriter.id
            LEFT JOIN MovieActor ON Movie.id = MovieActor.movie_id
            LEFT JOIN Person AS PersonActor ON MovieActor.person_id = PersonActor.id
            WHERE Movie.user_id = ?
        '''
        #GROUP BY Movie.id
        #ORDER BY {sort_by} {order}
    params = [user_id]
    # Add genre filter if provided
    if genre_filter:
        query += ' AND Movie.genre LIKE ?'
        params.append(f'%{genre_filter}%')
    # Add country filter if provided
    if country_filter:
        query += ' AND Movie.country LIKE ?'
        params.append(f'%{country_filter}%')

    # Add sorting
    query += f' GROUP BY Movie.id ORDER BY {sort_by} {order}'
    
    # Execute query with the dynamic parameters
    cur.execute(query, params)
    movies = cur.fetchall()


    return render_template('index.html', movies=movies, sort_by=sort_by, order=order, new_order=new_order, genre_filter=genre_filter, country_filter=country_filter, username=username)


@app.route('/movie/<int:movie_id>')
def movie_detail(movie_id):
    db = get_db()
    cur = db.cursor()

    # Retrieve the logged-in user's ID
    user_id = session['user_id']

    # Fetch movie details for the logged-in user
    cur.execute('''
        SELECT title, release_year, genre, rated, released, runtime, plot, language, country, awards, poster, imdbRating, imdbVotes, imdbID, type, totalSeasons
        FROM Movie 
        WHERE id = ? AND user_id = ?
    ''', (movie_id, user_id))
    movie = cur.fetchone()

    if movie is None:
        return "Movie not found or access denied", 404

    # Fetch directors associated with this movie
    cur.execute('''
        SELECT Person.id, Person.name 
        FROM MovieDirector
        JOIN Person ON MovieDirector.person_id = Person.id
        WHERE MovieDirector.movie_id = ? AND Person.user_id = ?
    ''', (movie_id, user_id))
    directors = cur.fetchall()

    # Fetch writers associated with this movie
    cur.execute('''
        SELECT Person.id, Person.name 
        FROM MovieWriter
        JOIN Person ON MovieWriter.person_id = Person.id
        WHERE MovieWriter.movie_id = ? AND Person.user_id = ?
    ''', (movie_id, user_id))
    writers = cur.fetchall()

    # Fetch actors associated with this movie, including their roles
    cur.execute('''
        SELECT Person.id, Person.name, MovieActor.role 
        FROM MovieActor
        JOIN Person ON MovieActor.person_id = Person.id
        WHERE MovieActor.movie_id = ? AND Person.user_id = ?
    ''', (movie_id, user_id))
    actors = cur.fetchall()
    imdb_id = movie['imdbID']
    comments = fetch_comments(imdb_id, 'movie')

    return render_template(
        'movie_detail.html', 
        movie_id=movie_id, 
        movie=movie, 
        directors=directors, 
        writers=writers, 
        actors=actors,
        comments=comments,
        imdbID=imdb_id
    )


@app.route('/person/<int:person_id>')
def person_detail(person_id):
    db = get_db()
    cur = db.cursor()
    
    user_id = session['user_id']
    # Retrieve person details directly from the database
    cur.execute('''
        SELECT name, birthday, image_url, bio, birthplace 
        FROM Person 
        WHERE id = ? AND user_id = ?
    ''', (person_id, user_id))
    person = cur.fetchone()
    if person is None:
        return "Person not found", 404
    name, birthday, image_url, bio, birthplace = person

    # Get all movies associated with this person
    cur.execute('''
        SELECT Movie.id, Movie.title, 'Director' AS role FROM MovieDirector
        JOIN Movie ON MovieDirector.movie_id = Movie.id
        WHERE MovieDirector.person_id = ? AND Movie.user_id = ?
        UNION
        SELECT Movie.id, Movie.title, 'Writer' AS role FROM MovieWriter
        JOIN Movie ON MovieWriter.movie_id = Movie.id
        WHERE MovieWriter.person_id = ? AND Movie.user_id = ?
        UNION
        SELECT Movie.id, Movie.title, MovieActor.role FROM MovieActor
        JOIN Movie ON MovieActor.movie_id = Movie.id
        WHERE MovieActor.person_id = ? AND Movie.user_id = ?
    ''', (person_id, user_id, person_id, user_id, person_id, user_id))
    movies = cur.fetchall()
    name = person['name']
    comments = fetch_comments(name, 'person')
    return render_template('person_detail.html', 
                         person_id=person_id, 
                         name=name, 
                         birthday=birthday, 
                         image_url=image_url, 
                         bio=bio, 
                         birthplace=birthplace,
                         movies=movies, 
                         person=person, 
                         comments=comments, 
                         person_name=name)

def add_person_if_not_exists(db, name):
    cur = db.cursor()
    user_id = session['user_id']
    cur.execute('SELECT id FROM Person WHERE name = ? AND user_id = ?', (name, user_id))
    
    #cur.execute('SELECT id FROM Person WHERE name = ?', (name,))
    person = cur.fetchone()
    
    # If person exists, return their ID
    if person:
        return person[0]

    # Fetch additional details for the new person using the fetch_person_data helper
    bio, image_url, birthday, birthplace = fetch_person_data(name)

    # Insert the new person with fetched details into the database
    cur.execute('''
        INSERT INTO Person (name, birthday, birthplace, image_url, bio, user_id)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (name, birthday, birthplace, image_url, bio, user_id))
    db.commit()

    return cur.lastrowid  # Return the new person ID



def fetch_person_data(name):
    """
    Fetch detailed biographical data from Wikipedia.
    Returns: bio, image_url, birthday, birthplace
    """
    bio, image_url, birthday, birthplace = fetch_wikipedia_summary(name)
    
    # If bio is too short, try to get a longer version
    if bio and len(bio) < 500:  # If bio is less than 500 characters
        try:
            # Get full article content
            url = f"https://en.wikipedia.org/api/rest_v1/page/html/{name.replace(' ', '_')}"
            response = requests.get(url)
            
            if response.status_code == 200:
                # Extract first few paragraphs
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, 'html.parser')
                paragraphs = soup.find_all('p')
                
                # Combine paragraphs until we have a decent length
                full_bio = ""
                for p in paragraphs:
                    if p.text.strip():  # Skip empty paragraphs
                        full_bio += p.text.strip() + " "
                        if len(full_bio) > 1000:  # Get at least 1000 characters
                            break
                
                if full_bio:
                    bio = full_bio.strip()
        except Exception as e:
            print(f"Error getting full bio: {e}")
    
    # Clean up the bio text
    if bio:
        # Remove citations [1], [2], etc.
        bio = re.sub(r'\[\d+\]', '', bio)
        # Remove extra whitespace
        bio = ' '.join(bio.split())
    
    return bio, image_url, birthday, birthplace


@app.route('/update_individual_person/<int:person_id>')
def update_individual_person(person_id):
    db = get_db()
    cur = db.cursor()
    
    # Fetch person details with missing data in the Person table for the given person_id
    cur.execute('SELECT id, name FROM Person WHERE (birthday IS NULL OR image_url IS NULL OR bio IS NULL) AND id = ?', (person_id,))
    person = cur.fetchone()

    if person is None:
        return "Person not found or already has complete data", 404

    person_id, name = person
    print(f"Fetching data for {name} with ID {person_id}")

    # Fetch data from Wikipedia
    bio, image_url, birthday, birthplace = fetch_person_data(name)

    # Update the Person table with the fetched details
    cur.execute('''
        UPDATE Person
        SET birthday = COALESCE(?, birthday),
            birthplace = COALESCE(?, birthplace),
            image_url = COALESCE(?, image_url),
            bio = COALESCE(?, bio)
        WHERE id = ?
    ''', (birthday, birthplace, image_url, bio, person_id))
    db.commit()
    print("Person data updated successfully in the database.")

    # Verify update by querying the database again
    cur.execute('SELECT bio, image_url, birthday, birthplace FROM Person WHERE id = ?', (person_id,))
    updated_person = cur.fetchone()
    print("Updated record in database:", updated_person)

    return "Person data updated successfully!"


@app.route('/update_people_data')
def update_people_data():
    db = get_db()
    cur = db.cursor()
    
    # Fetch all people with missing data in the Person table
    cur.execute('SELECT id, name FROM Person WHERE birthday IS NULL OR image_url IS NULL OR bio IS NULL')
    people = cur.fetchall()

    for person_id, name in people:
        print(f"Fetching data for {name} with ID {person_id}")

        # Fetch data from Wikipedia
        bio, image_url, birthday, birthplace = fetch_person_data(name)

        # Update the Person table with the fetched details if found
        cur.execute('''
            UPDATE Person
            SET birthday = COALESCE(?, birthday),
                birthplace = COALESCE(?, birthplace),
                image_url = COALESCE(?, image_url),
                bio = COALESCE(?, bio)
            WHERE id = ?
        ''', (birthday, birthplace, image_url, bio, person_id))
        db.commit()

        # Verify the update by querying the database again
        cur.execute('SELECT bio, image_url, birthday, birthplace FROM Person WHERE id = ?', (person_id,))
        updated_person = cur.fetchone()
        print(f"Updated record in database for {name}:", updated_person)

    return "People data updated successfully!"


@app.route('/update_rating/<int:movie_id>', methods=['POST'])
def update_rating(movie_id):
    user_id = session['user_id']
    user_rating = request.form.get('user_rating', type=float)
    db = get_db()
    cur = db.cursor()

    # Update user's rating
    cur.execute('UPDATE Movie SET user_rating = ? WHERE id = ? AND user_id = ?', (user_rating, movie_id, user_id))

    # Calculate average rating based on imdbID
    cur.execute('SELECT imdbID FROM Movie WHERE id = ?', (movie_id,))
    imdbID = cur.fetchone()[0]
    cur.execute('SELECT AVG(user_rating) FROM Movie WHERE imdbID = ?', (imdbID,))
    average_rating = cur.fetchone()[0]

    # Update MovieRating table
    cur.execute('REPLACE INTO MovieRating (imdbID, average_rating) VALUES (?, ?)', (imdbID, average_rating))
    db.commit()
    return redirect(url_for('index'))


@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('q', '')
    search_type = request.args.get('type', 'all')  # all, movie, person
    year = request.args.get('year', '')
    
    if not query and not year:
        return redirect(url_for('index'))
        
    db = get_db()
    cur = db.cursor()
    results = []
    
    # If year is specified, only search movies regardless of search_type
    if year:
        cur.execute('''
            SELECT DISTINCT id, title, release_year, genre, rated 
            FROM Movie 
            WHERE release_year = ? AND title LIKE ?
            GROUP BY id
        ''', (year, f'%{query}%'))
        movie_results = cur.fetchall()
        results.extend([{'type': 'movie', 'data': m} for m in movie_results])
    else:
        # If no year specified, follow normal search type logic
        if search_type == 'movie' or search_type == 'all':
            cur.execute('''
                SELECT DISTINCT id, title, release_year, genre, rated 
                FROM Movie 
                WHERE title LIKE ?
                GROUP BY id
            ''', (f'%{query}%',))
            movie_results = cur.fetchall()
            results.extend([{'type': 'movie', 'data': m} for m in movie_results])
        
        if search_type == 'person' or search_type == 'all':
            cur.execute('''
                SELECT DISTINCT p.id, p.name, p.birthday, p.birthplace 
                FROM Person p
                LEFT JOIN MovieActor ma ON p.id = ma.person_id
                LEFT JOIN MovieDirector md ON p.id = md.person_id
                LEFT JOIN Movie m ON p.id = m.producer_id
                WHERE p.name LIKE ?
                GROUP BY p.id
            ''', (f'%{query}%',))
            person_results = cur.fetchall()
            results.extend([{'type': 'person', 'data': p} for p in person_results])
    
    return render_template('search_results.html', 
                         query=query, 
                         search_type=search_type,
                         year=year, 
                         results=results)


@app.route('/delete_movie/<int:movie_id>', methods=['POST'])
def delete_movie(movie_id):
    db = get_db()
    cur = db.cursor()
    
    try:
        # First delete all associations
        cur.execute('DELETE FROM MovieDirector WHERE movie_id = ?', (movie_id,))
        cur.execute('DELETE FROM MovieWriter WHERE movie_id = ?', (movie_id,))
        cur.execute('DELETE FROM MovieActor WHERE movie_id = ?', (movie_id,))
        
        # Then delete the movie itself
        cur.execute('DELETE FROM Movie WHERE id = ?', (movie_id,))
        
        db.commit()
        return redirect(url_for('index'))
    except sqlite3.Error as e:
        print(f"Error deleting movie: {e}")
        return "Error deleting movie", 500




def update_all_average_ratings():
    db = get_db()
    cur = db.cursor()

    # Recalculate average ratings for all movies based on imdbID
    cur.execute('''
        INSERT INTO MovieRating (imdbID, average_rating)
        SELECT imdbID, AVG(user_rating)
        FROM Movie
        WHERE user_rating IS NOT NULL
        GROUP BY imdbID
        ON CONFLICT(imdbID) DO UPDATE SET average_rating = excluded.average_rating
    ''')
    db.commit()


@app.route('/comments/reply', methods=['POST'])
def reply_to_comment():
    db = get_db()
    cur = db.cursor()

    user_id = session['user_id']
    content = request.form['content']
    parent_comment_id = request.form['parent_comment_id']
    target_type = request.form['target_type']  # 'movie' or 'person'
    target_id = request.form['target_id']  # imdbID for movies, name for people

    cur.execute('''
        INSERT INTO Comments (content, user_id, target_id, target_type, parent_comment_id)
        VALUES (?, ?, ?, ?, ?)
    ''', (content, user_id, target_id, target_type, parent_comment_id))
    db.commit()

    return redirect(request.referrer)


@app.route('/comments/react', methods=['POST'])
def react_to_comment():
    db = get_db()
    cur = db.cursor()

    user_id = session['user_id']
    comment_id = request.form['comment_id']
    reaction_type = request.form['reaction_type']

    # Check if user already reacted
    cur.execute('''
        SELECT id FROM CommentReaction
        WHERE comment_id = ? AND user_id = ?
    ''', (comment_id, user_id))
    existing_reaction = cur.fetchone()

    if existing_reaction:
        # Update reaction
        cur.execute('''
            UPDATE CommentReaction
            SET reaction_type = ?
            WHERE id = ?
        ''', (reaction_type, existing_reaction['id']))
    else:
        # Add new reaction
        cur.execute('''
            INSERT INTO CommentReaction (comment_id, user_id, reaction_type)
            VALUES (?, ?, ?)
        ''', (comment_id, user_id, reaction_type))
    db.commit()

    return redirect(request.referrer)


@app.route('/comments/add', methods=['POST'])
def add_comment():
    db = get_db()
    cur = db.cursor()

    user_id = session['user_id']
    content = request.form['content']
    target_type = request.form['target_type']  # 'movie' or 'person'
    target_id = request.form['target_id']  # imdbID for movies, name for people
    parent_comment_id = request.form.get('parent_comment_id')  # For replies, optional

    cur.execute('''
        INSERT INTO Comments (content, user_id, target_id, target_type, parent_comment_id)
        VALUES (?, ?, ?, ?, ?)
    ''', (content, user_id, target_id, target_type, parent_comment_id))
    db.commit()

    return redirect(request.referrer)

@app.route('/fetch_replies', methods=['GET'])
def fetch_replies():
    parent_comment_id = request.args.get('parent_comment_id')
    db = get_db()
    cur = db.cursor()

    cur.execute('''
        SELECT Comments.id, Comments.content, Comments.timestamp, Users.username
        FROM Comments
        JOIN Users ON Comments.user_id = Users.id
        WHERE Comments.parent_comment_id = ?
        ORDER BY Comments.timestamp ASC
    ''', (parent_comment_id,))
    replies = cur.fetchall()

    return jsonify({'replies': [dict(reply) for reply in replies]})




def fetch_comments(target_id, target_type):
    db = get_db()
    cur = db.cursor()

    # Fetch main comments
    cur.execute('''
        SELECT Comments.id, Comments.content, Comments.timestamp, User.username, 
               (SELECT COUNT(*) FROM CommentReaction WHERE comment_id = Comments.id AND reaction_type = 'like') AS likes,
               (SELECT COUNT(*) FROM CommentReaction WHERE comment_id = Comments.id AND reaction_type = 'dislike') AS dislikes
        FROM Comments
        JOIN User ON Comments.user_id = User.id
        WHERE Comments.target_id = ? AND Comments.target_type = ? AND Comments.parent_comment_id IS NULL
        ORDER BY Comments.timestamp DESC
    ''', (target_id, target_type))
    comments = [dict(comment) for comment in cur.fetchall()]  # Convert rows to dictionaries

    # Fetch replies for each comment
    for comment in comments:
        cur.execute('''
            SELECT Comments.id, Comments.content, Comments.timestamp, User.username
            FROM Comments
            JOIN User ON Comments.user_id = User.id
            WHERE Comments.parent_comment_id = ?
            ORDER BY Comments.timestamp ASC
        ''', (comment['id'],))
        comment['replies'] = [dict(reply) for reply in cur.fetchall()]  # Convert replies to dictionaries

    return comments





if __name__ == '__main__':
    app.run(debug=True)
