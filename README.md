# White Elephant Game

A web-based White Elephant gift exchange game with a festive theme.

## Features

- Add multiple players and their gifts
- Random turn order generation
- Interactive gift stealing mechanics
- Gift freezing after 3 steals
- Festive UI with falling snow
- Mobile-friendly design

## Technical Stack

- Python 3.x
- Flask
- SQLAlchemy
- SQLite database
- HTML/CSS/JavaScript

## Local Development

1. Create a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python app.py
```

4. Visit http://localhost:5013 in your browser

## Deployment

The application is configured for deployment on Render.com or similar platforms.

Required files:
- requirements.txt
- Procfile
- gunicorn.conf.py
