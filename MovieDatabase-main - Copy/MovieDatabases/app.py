"""
Main Flask application for the Movie Database.
Features:
- Movie and person data management
- Integration with OMDb API for movies
- Integration with Wikipedia API for person details
- Database operations for storing and updating data
"""

import requests
from flask import Flask, request, render_template, request, g, redirect, url_for, flash
import sqlite3
import re
from datetime import datetime
from test import fetch_wikipedia_summary

app = Flask(__name__)
DATABASE = 'database.db'
OMDB_API_KEY = 'e45abe68'  # Your OMDb API key

# Function to get a database connection
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row # Return rows as dictionaries for easier access
    return db

# Close the database connection at the end of each request
@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.route('/fetch_movie', methods=['GET', 'POST'])
def fetch_movie():
    if request.method == 'POST':
        title = request.form['title']
        release_year = request.form['release_year']
        user_rating = request.form.get('user_rating', type=float)

        # First, get basic movie data
        omdb_url = f'http://www.omdbapi.com/?t={title}&y={release_year}&apikey={OMDB_API_KEY}'
        response = requests.get(omdb_url)
        movie_data = response.json()

        if movie_data.get('Response') == 'True':
            # Get full cast using IMDb ID
            full_cast_url = f'http://www.omdbapi.com/?i={movie_data.get("imdbID")}&apikey={OMDB_API_KEY}&type=movie&plot=full'
            full_cast_response = requests.get(full_cast_url)
            full_cast_data = full_cast_response.json()
            
            # Update actors list with full cast if available
            if full_cast_data.get('Actors'):
                movie_data['Actors'] = full_cast_data.get('Actors')

            db = get_db()
            cur = db.cursor()
            
            # Check if movie already exists
            cur.execute('SELECT id FROM Movie WHERE title = ? AND release_year = ?', 
                       (movie_data.get('Title'), movie_data.get('Year')))
            existing_movie = cur.fetchone()
            
            if existing_movie:
                # If movie exists, just update its data
                movie_id = existing_movie[0]
                cur.execute('''
                    UPDATE Movie 
                    SET genre = ?, rated = ?, released = ?, runtime = ?, plot = ?, 
                        language = ?, country = ?, awards = ?, poster = ?, 
                        imdbRating = ?, imdbVotes = ?, imdbID = ?, type = ?, 
                        totalSeasons = ?, user_rating = ?
                    WHERE id = ?
                ''', (
                    movie_data.get('Genre'), movie_data.get('Rated'),
                    movie_data.get('Released'), movie_data.get('Runtime'),
                    movie_data.get('Plot'), movie_data.get('Language'),
                    movie_data.get('Country'), movie_data.get('Awards'),
                    movie_data.get('Poster'), movie_data.get('imdbRating'),
                    movie_data.get('imdbVotes'), movie_data.get('imdbID'),
                    movie_data.get('Type'), movie_data.get('totalSeasons'),
                    user_rating, movie_id
                ))
            else:
                # If movie doesn't exist, insert it
                cur.execute('''
                    INSERT INTO Movie (title, release_year, genre, rated, released, 
                                     runtime, plot, language, country, awards, poster, 
                                     imdbRating, imdbVotes, imdbID, type, totalSeasons, 
                                     user_rating)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    movie_data.get('Title'), movie_data.get('Year'),
                    movie_data.get('Genre'), movie_data.get('Rated'),
                    movie_data.get('Released'), movie_data.get('Runtime'),
                    movie_data.get('Plot'), movie_data.get('Language'),
                    movie_data.get('Country'), movie_data.get('Awards'),
                    movie_data.get('Poster'), movie_data.get('imdbRating'),
                    movie_data.get('imdbVotes'), movie_data.get('imdbID'),
                    movie_data.get('Type'), movie_data.get('totalSeasons'),
                    user_rating
                ))
                movie_id = cur.lastrowid

            # Process directors, writers, and actors
            # Clear existing associations first
            cur.execute('DELETE FROM MovieDirector WHERE movie_id = ?', (movie_id,))
            cur.execute('DELETE FROM MovieWriter WHERE movie_id = ?', (movie_id,))
            cur.execute('DELETE FROM MovieActor WHERE movie_id = ?', (movie_id,))

            # Add new associations
            for director_name in movie_data.get('Director', '').split(', '):
                if director_name:
                    director_id = add_person_if_not_exists(db, director_name)
                    cur.execute('INSERT INTO MovieDirector (movie_id, person_id) VALUES (?, ?)', 
                              (movie_id, director_id))

            for writer_name in movie_data.get('Writer', '').split(', '):
                if writer_name:
                    writer_id = add_person_if_not_exists(db, writer_name)
                    cur.execute('INSERT INTO MovieWriter (movie_id, person_id) VALUES (?, ?)', 
                              (movie_id, writer_id))

            # When processing actors, split by both comma and 'and'
            actors_list = []
            raw_actors = movie_data.get('Actors', '').replace(' and ', ', ').split(', ')
            for actor_name in raw_actors:
                if actor_name and actor_name.strip():
                    actor_name = actor_name.strip()
                    actors_list.append(actor_name)
                    actor_id = add_person_if_not_exists(db, actor_name)
                    cur.execute('INSERT INTO MovieActor (movie_id, person_id, role) VALUES (?, ?, ?)', 
                              (movie_id, actor_id, "Actor"))

            db.commit()
            return redirect(url_for('index'))
        else:
            return f"Movie not found: {movie_data.get('Error')}", 404

    return render_template('fetch_movie.html')




@app.route('/update_movies', methods=['GET'])
def update_movies():
    db = get_db()
    cur = db.cursor()
    
    # Fetch all movies from the database
    cur.execute('SELECT id, title, release_year FROM Movie')
    movies = cur.fetchall()

    # Loop through each movie and update its data
    for movie in movies:
        movie_id, title, release_year = movie

        # Fetch updated data from OMDb API
        omdb_url = f'http://www.omdbapi.com/?t={title}&y={release_year}&apikey={OMDB_API_KEY}'
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
    return """
        <script>
            alert('All movies have been updated successfully!');
            window.location.href = '/';
        </script>
    """



@app.route('/update_individual_movie/<int:movie_id>', methods=['GET'])
def update_individual_movie(movie_id):
    db = get_db()
    cur = db.cursor()
    
    # Fetch the specific movie from the database
    cur.execute('SELECT id, title, release_year FROM Movie WHERE id = ?', (movie_id,))
    movie = cur.fetchone()

    if movie is None:
        return "Movie not found", 404

    movie_id, title, release_year = movie

    # First get basic movie data
    omdb_url = f'http://www.omdbapi.com/?t={title}&y={release_year}&apikey={OMDB_API_KEY}'
    response = requests.get(omdb_url)
    movie_data = response.json()

    if movie_data.get('Response') == 'True':
        # Get full cast using IMDb ID
        full_cast_url = f'http://www.omdbapi.com/?i={movie_data.get("imdbID")}&apikey={OMDB_API_KEY}&type=movie&plot=full'
        full_cast_response = requests.get(full_cast_url)
        full_cast_data = full_cast_response.json()
        
        # Update actors list with full cast if available
        if full_cast_data.get('Actors'):
            movie_data['Actors'] = full_cast_data.get('Actors')

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

        # Clear existing associations
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

        # Update actors - handle full cast
        actors_list = movie_data.get('Actors', '').replace(' and ', ', ').split(', ')
        for actor_name in actors_list:
            if actor_name and actor_name.strip():
                actor_name = actor_name.strip()
                actor_id = add_person_if_not_exists(db, actor_name)
                cur.execute('INSERT INTO MovieActor (movie_id, person_id, role) VALUES (?, ?, ?)', 
                          (movie_id, actor_id, "Actor"))

        db.commit()
        return redirect(url_for('movie_detail', movie_id=movie_id))

    return "Failed to update movie", 404


"""@app.route('/')
def index():
    sort_by = request.args.get('sort_by', 'title')  # Default sort by 'title'
    order = request.args.get('order', 'asc')  # Default order is ascending

    # Ensure sort_by is one of the allowed fields to prevent SQL injection
    allowed_fields = ['title', 'release_year', 'genre', 'rated', 'imdbRating']
    if sort_by not in allowed_fields:
        sort_by = 'title'

    # Toggle order for the next click
    new_order = 'desc' if order == 'asc' else 'asc'

    db = get_db()
    cur = db.cursor()

    # Use SUBSTR to get the first year in case of ranges (e.g., 2019–2020)
    if sort_by == 'release_year':
        query = f'''
            SELECT id, title, SUBSTR(release_year, 1, 4) AS release_year, genre, rated, imdbRating,
                   director, writer, actors
            FROM Movie
            ORDER BY release_year {order}
        '''
    else:
        query = f'''
            SELECT id, title, release_year, genre, rated, imdbRating,
                   director, writer, actors
            FROM Movie
            ORDER BY {sort_by} {order}
        '''

    cur.execute(query)
    movies = cur.fetchall()
    return render_template('index.html', movies=movies, sort_by=sort_by, new_order=new_order)
"""
@app.route('/')
def index():
    sort_by = request.args.get('sort_by', 'title')  # Default to 'title'
    order = request.args.get('order', 'asc')  # Default order is ascending
    new_order = 'desc' if order == 'asc' else 'asc'

    # Ensure sort_by is one of the allowed fields to prevent SQL injection
    allowed_fields = ['title', 'release_year', 'genre', 'rated', 'imdbRating', 'country', 'user_rating']
    sort_by = sort_by if sort_by in allowed_fields else 'title'
    order = order if order in ['asc', 'desc'] else 'asc'

    db = get_db()
    cur = db.cursor()

    # Build query based on whether sorting by release_year or another field
    if sort_by == 'release_year':
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
            GROUP BY Movie.id
            ORDER BY SUBSTR(Movie.release_year, 1, 4) {order}
        '''
    else:
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
            GROUP BY Movie.id
            ORDER BY {sort_by} {order}
        '''
    
    # Execute the query
    cur.execute(query)
    movies = cur.fetchall()

    return render_template('index.html', movies=movies, sort_by=sort_by, order=order, new_order=new_order)



"""# Route to display detailed information about a single movie
@app.route('/movie/<int:movie_id>')
def movie_detail(movie_id):
    db = get_db()
    cur = db.cursor()
    cur.execute('SELECT title, release_year, genre, rated, released, runtime, plot, language, country, awards, poster, imdbRating, imdbVotes, imdbID, type, totalSeasons, director, writer, actors FROM Movie WHERE id = ?', (movie_id,))
    movie = cur.fetchone()
    return render_template('movie_detail.html', movie=movie)"""


@app.route('/movie/<int:movie_id>')
def movie_detail(movie_id):
    db = get_db()
    cur = db.cursor()

    # Fetch movie details
    cur.execute('''
        SELECT title, release_year, genre, rated, released, runtime, plot, language, country, awards, poster, imdbRating, imdbVotes, imdbID, type, totalSeasons
        FROM Movie WHERE id = ?
    ''', (movie_id,))
    movie = cur.fetchone()

    # Fetch directors associated with this movie
    cur.execute('''
        SELECT Person.id, Person.name FROM MovieDirector
        JOIN Person ON MovieDirector.person_id = Person.id
        WHERE MovieDirector.movie_id = ?
    ''', (movie_id,))
    directors = cur.fetchall()

    # Fetch writers associated with this movie
    cur.execute('''
        SELECT Person.id, Person.name FROM MovieWriter
        JOIN Person ON MovieWriter.person_id = Person.id
        WHERE MovieWriter.movie_id = ?
    ''', (movie_id,))
    writers = cur.fetchall()

    # Fetch actors associated with this movie, including their roles
    cur.execute('''
        SELECT Person.id, Person.name, MovieActor.role FROM MovieActor
        JOIN Person ON MovieActor.person_id = Person.id
        WHERE MovieActor.movie_id = ?
    ''', (movie_id,))
    actors = cur.fetchall()

    return render_template('movie_detail.html', movie_id=movie_id, movie=movie, directors=directors, writers=writers, actors=actors)


"""
Route to display detailed information about a person.
- Fetches person data from database
- Automatically refreshes data from Wikipedia if needed
- Shows associated movies and roles
- Handles cases where database schema might be incomplete
"""
@app.route('/person/<int:person_id>')
def person_detail(person_id):
    db = get_db()
    cur = db.cursor()
    
    # First, try to refresh the person's data
    refresh_person_data(person_id)
    
    # Retrieve person details with all fields
    try:
        cur.execute('''
            SELECT name, birthday, birthplace, image_url, bio, last_updated 
            FROM Person 
            WHERE id = ?
        ''', (person_id,))
    except sqlite3.OperationalError:
        # If last_updated column doesn't exist, query without it
        cur.execute('''
            SELECT name, birthday, birthplace, image_url, bio 
            FROM Person 
            WHERE id = ?
        ''', (person_id,))
    
    person = cur.fetchone()
    
    if person is None:
        return "Person not found", 404
    
    # Handle both cases (with and without last_updated)
    if len(person) == 6:
        name, birthday, birthplace, image_url, bio, last_updated = person
    else:
        name, birthday, birthplace, image_url, bio = person
        last_updated = None

    # Get all movies associated with this person
    cur.execute('''
        SELECT Movie.id, Movie.title, 'Director' AS role FROM MovieDirector
        JOIN Movie ON MovieDirector.movie_id = Movie.id
        WHERE MovieDirector.person_id = ?
        UNION
        SELECT Movie.id, Movie.title, 'Writer' AS role FROM MovieWriter
        JOIN Movie ON MovieWriter.movie_id = Movie.id
        WHERE MovieWriter.person_id = ?
        UNION
        SELECT Movie.id, Movie.title, MovieActor.role FROM MovieActor
        JOIN Movie ON MovieActor.movie_id = Movie.id
        WHERE MovieActor.person_id = ?
        ORDER BY title
    ''', (person_id, person_id, person_id))
    movies = cur.fetchall()

    return render_template('person_detail.html', 
                         person_id=person_id,
                         name=name,
                         birthday=birthday,
                         birthplace=birthplace,
                         image_url=image_url,
                         bio=bio,
                         last_updated=last_updated,
                         movies=movies)


"""
Helper function to manage person records.
- Checks if person exists in database
- Fetches data from Wikipedia for new persons
- Handles data insertion with proper error checking
"""
def add_person_if_not_exists(db, name):
    cur = db.cursor()
    cur.execute('SELECT id FROM Person WHERE name = ?', (name,))
    person = cur.fetchone()
    
    # If person exists, return their ID
    if person:
        return person[0]

    # Fetch additional details for the new person using the fetch_person_data helper
    bio, image_url, birthday, birthplace = fetch_person_data(name)

    # Insert the new person with fetched details into the database
    cur.execute('''
        INSERT INTO Person (name, birthday, birthplace, image_url, bio)
        VALUES (?, ?, ?, ?, ?)
    ''', (name, birthday, birthplace, image_url, bio))
    db.commit()

    return cur.lastrowid  # Return the new person ID



@app.route('/update_rating/<int:movie_id>', methods=['POST'])
def update_rating(movie_id):
    user_rating = request.form.get('user_rating', type=float)
    sort_by = request.form.get('sort_by', 'title')  # Default to 'title' if not provided
    order = request.form.get('order', 'asc')  # Default to 'asc' if not provided

    db = get_db()
    cur = db.cursor()
    
    # Update the user rating for the specified movie
    cur.execute('UPDATE Movie SET user_rating = ? WHERE id = ?', (user_rating, movie_id))
    db.commit()
    
    # Redirect to index with the same sorting parameters
    return redirect(url_for('index', sort_by=sort_by, order=order))


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

    db.commit()
    return """
        <script>
            alert('All people data has been updated successfully!');
            window.location.href = '/';
        </script>
    """


"""
Updates person data from Wikipedia.
- Fetches fresh data for birthdays, birthplaces, etc.
- Handles database schema variations
- Uses COALESCE to keep existing data if new data is unavailable
"""
def refresh_person_data(person_id):
    """Refresh person data from Wikipedia"""
    db = get_db()
    cur = db.cursor()
    
    # Get person's current data
    cur.execute('SELECT name FROM Person WHERE id = ?', (person_id,))
    result = cur.fetchone()
    
    if not result:
        return False
        
    name = result[0]
    
    # Fetch new data
    bio, image_url, birthday, birthplace = fetch_person_data(name)
    
    try:
        # Try updating with last_updated
        cur.execute('''
            UPDATE Person 
            SET bio = COALESCE(?, bio),
                image_url = COALESCE(?, image_url),
                birthday = COALESCE(?, birthday),
                birthplace = COALESCE(?, birthplace),
                last_updated = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (bio, image_url, birthday, birthplace, person_id))
    except sqlite3.OperationalError:
        # If last_updated column doesn't exist, update without it
        cur.execute('''
            UPDATE Person 
            SET bio = COALESCE(?, bio),
                image_url = COALESCE(?, image_url),
                birthday = COALESCE(?, birthday),
                birthplace = COALESCE(?, birthplace)
            WHERE id = ?
        ''', (bio, image_url, birthday, birthplace, person_id))
    
    db.commit()
    return True


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


if __name__ == '__main__':
    app.run(debug=True)