-- Create Person Table to store details of all individuals (directors, writers, actors)
CREATE TABLE IF NOT EXISTS Person (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    birthday TEXT,  -- Added birthday column
    birthplace TEXT,  -- Added birthplace column
    image_url TEXT,
    bio TEXT
);

-- Create Movie Table with OMDb fields
CREATE TABLE IF NOT EXISTS Movie (
    id INTEGER PRIMARY KEY,
    title VARCHAR(100) NOT NULL,
    release_year INTEGER NOT NULL,
    genre VARCHAR(50),
    rated VARCHAR(10),
    released VARCHAR(20),
    runtime VARCHAR(50),
    plot TEXT,
    language VARCHAR(50),
    country VARCHAR(50),
    awards VARCHAR(100),
    poster VARCHAR(255),
    imdbRating VARCHAR(10),
    imdbVotes VARCHAR(20),
    imdbID VARCHAR(20),
    type VARCHAR(20),
    totalSeasons VARCHAR(10),
    producer_id INTEGER,
    user_rating FLOAT,
    FOREIGN KEY (producer_id) REFERENCES Person(id)
);


-- Association Tables to link Movies and People by Role

-- MovieDirector table linking a movie to its directors
CREATE TABLE IF NOT EXISTS MovieDirector (
    movie_id INTEGER,
    person_id INTEGER,
    FOREIGN KEY (movie_id) REFERENCES Movie(id),
    FOREIGN KEY (person_id) REFERENCES Person(id)
);

-- MovieWriter table linking a movie to its writers
CREATE TABLE IF NOT EXISTS MovieWriter (
    movie_id INTEGER,
    person_id INTEGER,
    FOREIGN KEY (movie_id) REFERENCES Movie(id),
    FOREIGN KEY (person_id) REFERENCES Person(id)
);

-- MovieActor table linking a movie to its actors, with role information
CREATE TABLE IF NOT EXISTS MovieActor (
    movie_id INTEGER,
    person_id INTEGER,
    role VARCHAR(100),
    FOREIGN KEY (movie_id) REFERENCES Movie(id),
    FOREIGN KEY (person_id) REFERENCES Person(id)
);

