-- Create User Table
CREATE TABLE "user" (
    id SERIAL PRIMARY KEY,
    username VARCHAR(150) UNIQUE NOT NULL,
    password VARCHAR(150) NOT NULL,
    is_admin BOOLEAN DEFAULT FALSE
);

-- Create Website Table
CREATE TABLE website (
    id SERIAL PRIMARY KEY,
    domain VARCHAR(255) NOT NULL,
    title VARCHAR(255),
    icp VARCHAR(255),
    server VARCHAR(255),
    screenshot_path VARCHAR(500)
);

-- Create Annotation Table
CREATE TABLE annotation (
    id SERIAL PRIMARY KEY,
    website_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    label VARCHAR(100) NOT NULL,
    timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_website FOREIGN KEY (website_id) REFERENCES website (id),
    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES "user" (id)
);
