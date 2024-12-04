CREATE TABLE IF NOT EXISTS Person (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    birthday TEXT,  -- Added birthday column
    birthplace TEXT,  -- Added birthplace column
    image_url TEXT,
    bio TEXT,
    user_id INTEGER  -- Included user_id directly
);

CREATE TABLE IF NOT EXISTS User (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL
);

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
    user_id INTEGER,  -- Included user_id directly
    FOREIGN KEY (producer_id) REFERENCES Person(id)
);

CREATE TABLE IF NOT EXISTS MovieDirector (
    movie_id INTEGER,
    person_id INTEGER,
    FOREIGN KEY (movie_id) REFERENCES Movie(id),
    FOREIGN KEY (person_id) REFERENCES Person(id)
);

CREATE TABLE IF NOT EXISTS MovieWriter (
    movie_id INTEGER,
    person_id INTEGER,
    FOREIGN KEY (movie_id) REFERENCES Movie(id),
    FOREIGN KEY (person_id) REFERENCES Person(id)
);

CREATE TABLE IF NOT EXISTS MovieActor (
    movie_id INTEGER,
    person_id INTEGER,
    role VARCHAR(100),
    FOREIGN KEY (movie_id) REFERENCES Movie(id),
    FOREIGN KEY (person_id) REFERENCES Person(id)
);


CREATE TABLE IF NOT EXISTS MovieRating (
    imdbID TEXT PRIMARY KEY,  -- Ensure imdbID is unique
    average_rating FLOAT NOT NULL
);

CREATE TABLE IF NOT EXISTS Comment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    target_type TEXT NOT NULL, -- 'movie' or 'person'
    target_id INTEGER NOT NULL, -- Movie ID or Person ID
    content TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES User(id)
);

CREATE TABLE IF NOT EXISTS CommentReaction (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    comment_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    reaction_type TEXT NOT NULL, -- 'like' or 'dislike'
    FOREIGN KEY (comment_id) REFERENCES Comment(id),
    FOREIGN KEY (user_id) REFERENCES User(id)
);

CREATE TABLE IF NOT EXISTS CommentReply (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_comment_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_comment_id) REFERENCES Comment(id),
    FOREIGN KEY (user_id) REFERENCES User(id)
);
CREATE TABLE IF NOT EXISTS Comment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_type TEXT NOT NULL, -- 'movie' or 'person'
    target_id TEXT NOT NULL, -- imdbID for movies or person_id for people
    content TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER NOT NULL,
    FOREIGN KEY (user_id) REFERENCES User(id)
);
DROP TABLE IF EXISTS Comment;
DROP TABLE IF EXISTS CommentReaction;
DROP TABLE IF EXISTS CommentReply;
CREATE TABLE IF NOT EXISTS Comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    target_id TEXT NOT NULL, -- imdbID for movies or name for people
    target_type TEXT CHECK(target_type IN ('movie', 'person')) NOT NULL,
    parent_comment_id INTEGER,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES Users (id),
    FOREIGN KEY (parent_comment_id) REFERENCES Comments (id)
);

CREATE TABLE IF NOT EXISTS CommentReaction (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    comment_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    reaction_type TEXT CHECK(reaction_type IN ('like', 'dislike')) NOT NULL,
    FOREIGN KEY (comment_id) REFERENCES Comments (id),
    FOREIGN KEY (user_id) REFERENCES Users (id),
    UNIQUE (comment_id, user_id)
);

CREATE TABLE IF NOT EXISTS CommentReply (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_comment_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_comment_id) REFERENCES Comments (id),
    FOREIGN KEY (user_id) REFERENCES Users (id)
);
