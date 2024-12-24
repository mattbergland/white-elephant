from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import random
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'dev-key-for-local')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///white_elephant.db'
db = SQLAlchemy(app)

class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    gift_description = db.Column(db.String(200))
    current_gift = db.Column(db.Integer)
    turn_order = db.Column(db.Integer)
    has_played = db.Column(db.Boolean, default=False)
    is_last_player = db.Column(db.Boolean, default=False)

class Gift(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200))
    current_holder = db.Column(db.Integer, db.ForeignKey('player.id'))
    times_stolen = db.Column(db.Integer, default=0)
    is_frozen = db.Column(db.Boolean, default=False)
    original_opener = db.Column(db.Integer, db.ForeignKey('player.id'))

with app.app_context():
    db.create_all()

# Global variables
current_turn = 0
game_started = False
game_complete = False
next_player_after_steal = None
last_stolen_gift_id = None

@app.route('/')
def index():
    players = Player.query.all()
    gifts = Gift.query.all()
    current_player = Player.query.filter_by(turn_order=current_turn).first() if game_started else None
    
    # Check if all players have gifts and have played
    all_players_have_gifts = all(player.current_gift is not None for player in players)
    all_players_played = all(player.has_played for player in players)
    
    global game_complete
    if all_players_have_gifts and all_players_played and next_player_after_steal is None:
        game_complete = True
    
    return render_template('index.html', 
                         players=players, 
                         gifts=gifts, 
                         game_started=game_started,
                         game_complete=game_complete,
                         current_player=current_player,
                         last_stolen_gift_id=last_stolen_gift_id,
                         next_player_after_steal=next_player_after_steal,
                         Player=Player,
                         Gift=Gift)

@app.route('/add_player', methods=['POST'])
def add_player():
    if game_started:
        flash('Cannot add players after game has started!')
        return redirect(url_for('index'))
    
    name = request.form.get('name')
    gift_description = request.form.get('gift')
    
    player = Player(name=name, gift_description=gift_description)
    db.session.add(player)
    db.session.commit()
    
    flash(f'Added {name} to the game!')
    return redirect(url_for('index'))

@app.route('/start_game', methods=['POST'])
def start_game():
    global current_turn, game_started, game_complete, next_player_after_steal, last_stolen_gift_id
    
    players = Player.query.all()
    if len(players) < 3:
        flash('Need at least 3 players to start!')
        return redirect(url_for('index'))
    
    # Reset game state
    game_started = True
    game_complete = False
    next_player_after_steal = None
    last_stolen_gift_id = None
    
    # Reset all players and create gifts
    for player in players:
        player.current_gift = None
        player.has_played = False
        player.is_last_player = False
        # Create a gift for each player
        gift = Gift(description=player.gift_description)
        db.session.add(gift)
    
    # Assign random turn order
    turn_orders = list(range(len(players)))
    random.shuffle(turn_orders)
    for i, player in enumerate(players):
        player.turn_order = turn_orders[i]
    
    # Mark the last player
    last_player = Player.query.filter_by(turn_order=len(players)-1).first()
    last_player.is_last_player = True
    
    # Set the first turn
    current_turn = 0
    
    db.session.commit()
    first_player = Player.query.filter_by(turn_order=current_turn).first()
    flash(f'Game started! {first_player.name} goes first!')
    return redirect(url_for('index'))

@app.route('/take_turn', methods=['POST'])
def take_turn():
    global current_turn, last_stolen_gift_id, game_complete, next_player_after_steal
    
    if not game_started:
        flash('Game has not started yet!')
        return redirect(url_for('index'))
    
    if game_complete:
        flash('Game is complete! Click Reset Game to start a new game.')
        return redirect(url_for('index'))
    
    action = request.form.get('action')
    gift_id = request.form.get('gift_id')
    current_player = Player.query.filter_by(turn_order=current_turn).first()
    
    if action == 'open':
        # Take a new gift
        available_gifts = Gift.query.filter_by(current_holder=None).all()
        if available_gifts:
            gift = random.choice(available_gifts)
            gift.current_holder = current_player.id
            gift.original_opener = current_player.id
            current_player.current_gift = gift.id
            current_player.has_played = True
            flash(f'{current_player.name} opened a new gift: {gift.description}')
            last_stolen_gift_id = None
            
            # Move to next player in sequence only if this wasn't a player who just had their gift stolen
            if next_player_after_steal and next_player_after_steal.id == current_player.id:
                next_player_after_steal = None
                current_turn = (current_player.turn_order + 1) % Player.query.count()
            elif not next_player_after_steal:
                current_turn = (current_player.turn_order + 1) % Player.query.count()
        else:
            flash('No more unopened gifts available!')
            return redirect(url_for('index'))
    
    elif action == 'steal':
        if not gift_id:
            flash('No gift selected to steal!')
            return redirect(url_for('index'))
            
        gift = Gift.query.get(gift_id)
        if not gift:
            flash('Invalid gift selected!')
            return redirect(url_for('index'))
            
        if gift.current_holder == current_player.id:
            flash("You can't steal your own gift!")
            return redirect(url_for('index'))
            
        # Check if gift can be stolen
        if not gift.is_frozen and gift.times_stolen < 3:
            # Check if this gift was just stolen
            if last_stolen_gift_id and int(gift_id) == last_stolen_gift_id:
                flash("You can't steal back the gift that was just stolen from you!")
                return redirect(url_for('index'))
                
            previous_holder = Player.query.get(gift.current_holder)
            if not previous_holder:
                flash('Error: Could not find the previous gift holder!')
                return redirect(url_for('index'))
            
            # Handle stealing logic
            old_gift = current_player.current_gift
            current_player.current_gift = gift.id
            previous_holder.current_gift = None  # Set to None so they can open a new gift
            previous_holder.has_played = False  # Allow them to play again
            gift.times_stolen += 1
            current_player.has_played = True
            
            # If gift has been stolen 3 times, freeze it
            if gift.times_stolen >= 3:
                gift.is_frozen = True
                flash(f'This gift has been stolen 3 times and is now frozen!')
            
            flash(f'{current_player.name} stole a gift from {previous_holder.name}!')
            last_stolen_gift_id = gift.id
            
            # The person who lost their gift gets the next turn
            next_player_after_steal = previous_holder
            current_turn = previous_holder.turn_order
            flash(f'{previous_holder.name} gets the next turn since their gift was stolen!')
            
            # Special case: If this is the last player's turn and they steal
            if current_player.is_last_player and gift.original_opener:
                original_opener = Player.query.get(gift.original_opener)
                if original_opener and original_opener.id != current_player.id:
                    next_player_after_steal = None  # Clear this so we don't conflict with last player rule
                    flash(f'{original_opener.name} gets one final turn since their gift was stolen by the last player!')
                    current_turn = original_opener.turn_order
        else:
            if gift.is_frozen:
                flash('This gift is frozen and cannot be stolen!')
            else:
                flash('This gift has been stolen the maximum number of times!')
            return redirect(url_for('index'))
    
    db.session.commit()
    
    # Check if game should end - only if no pending stolen gift turns
    players = Player.query.all()
    if all(player.current_gift is not None for player in players) and all(player.has_played for player in players) and next_player_after_steal is None:
        game_complete = True
        flash('Game Complete! Everyone has a gift. Click Reset Game to start a new game.')
    
    return redirect(url_for('index'))

@app.route('/reset_game', methods=['POST'])
def reset_game():
    global current_turn, game_started, game_complete, next_player_after_steal, last_stolen_gift_id
    
    # Reset game state
    current_turn = 0
    game_started = False
    game_complete = False
    next_player_after_steal = None
    last_stolen_gift_id = None
    
    # Delete all players and gifts
    Player.query.delete()
    Gift.query.delete()
    db.session.commit()
    
    flash('Game has been reset! Add new players to start a new game.')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5013, debug=True)
