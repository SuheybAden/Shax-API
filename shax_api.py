import asyncio
from enum import Enum
import random
import websockets
from websockets.server import WebSocketServerProtocol
import json
import secrets

from board_manager import BoardManager, GameState


# Bit masks
# The game_type parameter in the "join_game" JSON request is formatted as follows:
#       | 32 bits for private lobby key | 
LOCAL_GAME_MASK = 0b1
CPU_GAME_MASK = 0b10
PRIV_GAME_MASK = 0b100
LOBBY_KEY_MASK = ~0xFFFF

# Game type (key) -> Player websocket(value)
game_types: dict = {}

# dict of player websockets that are in the waiting list
waiting_list: dict = {}

# BoardManager (key) -> List of Player Websockets (value)
games: dict = {}

# Player Websocket(key) -> List containing the BoardManager, opposing player, and the player's token (value)
players: dict = {}


class EndFlags(Enum):
    GAME_NOT_STARTED = 0,
    QUIT_QUEUE = 1,
    PLAYER_WON = 2,
    PLAYER_QUIT = 3,
    PLAYER_DISCONNECTED = 4

# Takes in a new connection looking for a game.
# If the waiting list has another connection waiting for the same type of game,
# a new game is started between it and the new connection.
# Otherwise, the new connection is put into the waiting list
async def join_game(connection, params):
    # Generate a default API response
    response = {
        "success": False,
        "action": "join_game",
        "error": "",
        "waiting": False,
        "lobby_key": 0,
        "player1_key": 0,
        "player2_key": 0,
        "player_num": 0,
        "adjacent_pieces": {},
        "next_state": GameState.STOPPED.name,
        "next_player": 0
    }

    # Load all the necessary parameters
    try:
        game_type: int = params["game_type"]
    except Exception:
        response["error"] = "Wasn't given all the necessary parameters for joining a game"
        await connection.send(json.dumps(response))
        return

    # Check if the connection is requesting to join a private lobby
    joining_lobby = (bool)(game_type & LOBBY_KEY_MASK)
    # Check if the connection is requesting to create a private game lobby
    create_lobby = (bool)(game_type & PRIV_GAME_MASK)
    # Check if the connection is requesting for a game against a CPU
    requesting_CPU = (bool)(game_type & CPU_GAME_MASK)
    # Check if the connection is requesting for a local game
    is_local = (bool)(game_type & LOCAL_GAME_MASK)

    # Checks if the player is already in a game
    if connection in players:
        response["error"] = "The player is already in a game"
        await connection.send(json.dumps(response))

    # Checks if the player is already waiting for a game
    elif connection in waiting_list:
        response["error"] = "The player is already in the waiting list"
        await connection.send(json.dumps(response))

    # Tries to start a new game using the current connection
    # A new game can be started under 2 conditions:
    # 1) The current connection is requesting a game type that a previous connection already asked for
    # 2) The current connection is requesting a local game (aka both players originate from the same connection)
    elif game_type in game_types or is_local:
        # Initializes a new instance of the board manager
        game_manager: BoardManager = BoardManager(min_pieces=2, max_pieces=12)
        response["next_player"] = game_manager.start_game()

        # Loads the adjacent pieces array into a JSON-compatible format
        # so that the client knows how the board is arranged
        adjacent_pieces_json = []
        for node, neighbors in game_manager.adjacent_pieces.items():
            neighbors_array = []

            for neighbor in neighbors:
                neighbors_array.append({"x": neighbor[0], "y": neighbor[1]})

            adjacent_pieces_json.append({"x": node[0], "y": node[1], "neighbors": neighbors_array})

        # Update the JSON response for the current connection
        response["next_state"] = game_manager.game_state.name
        response["adjacent_pieces"] = adjacent_pieces_json
        response["success"] = True

        # Reuses the same connection for the opponent if this is a local game
        if is_local:
            opponent = connection

        # Otherwise, find the other player and remove them from the waiting list
        else:
            opponent = game_types.pop(game_type)
            waiting_list.pop(opponent)

            # Notify the second player (opponent) that the game has started
            response["player_num"] = 1
            await opponent.send(json.dumps(response))

        # Notify the first player that a game has started
        await connection.send(json.dumps(response))

        # Update all references to the relevant connections and game manager
        games[game_manager] = (connection, opponent)
        players[connection] = (game_manager, opponent, 0)
        players[opponent] = (game_manager, connection, 1)

    # Checks if the current connection is trying to join an unknown private lobby
    elif joining_lobby:
        response["error"] = "Your private lobby key is invalid"
        await connection.send(json.dumps(response))

    # If there are no available opponents, add the current connection to the waiting list
    else:
        # TODO: check if the "game_type" variable can be a 64-bit int
        # If the connection wants a private lobby or to go against a CPU opponent,
        # add a random "lobby key" to the front of the game type
        if requesting_CPU or create_lobby:
            lobby_key = random.randint(2**16, 2**32)
            game_type = (lobby_key << 16) | (game_type & 0xFFFF)
            response["lobby_key"] = game_type

        # Add the new connection to the waiting list
        game_types[game_type] = connection
        waiting_list[connection] = game_type

        response["success"] = True
        response["waiting"] = True
        await connection.send(json.dumps(response))


# Remove any references to the connection
async def close_connection(connection, flag: EndFlags):
    # Generate the defualt API response
    result = {"success": True,
              "action": "quit_game",
              "error": "",
              "flag": flag.value,
              "winner": 0}

    # If they were in a game, remove any remaining references to the player and their opponent
    if connection in players:
        board_manager, opponent, player_num = players.pop(connection, None)
        board_manager.end_game()

        # Check if it was a local game
        is_local = connection == opponent

        if not is_local:
            players.pop(opponent, None)

            # Tell the other player that their opponent left
            result["msg"] = "Opponent Forfeited."
            await opponent.send(json.dumps(result))

            # Generate message for telling the player that they forfeited
            result["msg"] = "You Forfeited."

    # Remove any references to the closed connection in the waiting list
    elif connection in waiting_list:
        game_type = waiting_list.pop(connection)
        game_types.pop(game_type)

        result["flag"] = EndFlags.QUIT_QUEUE.value

    else:
        # Generate the message for telling the player that they left the waiting list
        result["success"] = False
        result["error"] = "You are neither in a waiting list or game"
        result["flag"] = EndFlags.GAME_NOT_STARTED.value

    return result


async def handler(connection):
    print("There's a new connection from ", connection.remote_address[0], "!")

    try:
        async for message in connection:
            # Padding for debug prints
            print("")

            params = json.loads(message)

            # FOR TESTING PURPOSES
            if "test" in params:
                await connection.send(json.dumps({}))
                continue

            # Get the action that the player wants to perform
            try:
                action: str = params["action"]
            except Exception:
                response = {
                    "success": False,
                    "error": "The \"action\" property could not be found in your JSON request"
                }
                await connection.send(json.dumps(response))
                continue

            # START GAME CASE
            if action == "join_game":
                print("A player is trying to join a game")

                # Tries connecting a new player to a game
                await join_game(connection, params)

            # QUIT GAME CASE
            elif action == "quit_game":
                print("A player is trying to quit a game")
                response = await close_connection(connection, EndFlags.PLAYER_QUIT)

                # Notify the player of the outcome
                await connection.send(json.dumps(response))

            # GAME RELATED CASES
            else:
                game_manager, opponent, player_num = players.get(connection, [None, None, None])

                # Check if the player is in a game
                if game_manager is None:
                    response = {
                        "success": False,
                        "action": action,
                        "error": "The player isn't in a game yet"
                    }
                    await connection.send(json.dumps(response))
                    continue

                # For local games, always set the player_num key to the current turn
                # This is b/c there is no way of accurately differentiating the two players
                # since they come from the same connection. So we have to assume that the one
                # requesting the move is the player whose turn it currently is.
                if connection == opponent:
                    player_num = game_manager.current_turn

                # PLACE PIECE CASE
                if action == "place_piece":
                    # Check that the request contains all the required keys
                    required_keys = ("x", "y")
                    if not all(key in params for key in required_keys):
                        print("Couldn't load all the necessary parameters")
                        continue

                    # Pass the player's action to the game manager
                    new_ID, x, y, active_pieces, error = game_manager.place_piece(
                        params["x"], params["y"], player_num)

                    # Generate a JSON response about the move's outcome
                    result = {"success": error == "",
                              "action": "place_piece",
                              "error": error,
                              "board_state": game_manager.board_state.tolist(),
                              "new_piece_ID": new_ID,
                              "new_x": x,
                              "new_y": y,
                              "active_pieces": active_pieces,
                              "next_player": game_manager.current_turn,
                              "next_state": game_manager.game_state.name}

                # REMOVE PIECE CASE
                elif action == "remove_piece":
                    # Check that the request contains all the required keys
                    required_keys = ["piece_ID"]
                    if not all(key in params for key in required_keys):
                        print("Couldn't load all the necessary parameters")
                        continue

                    # Pass the player's action to the game manager
                    piece_ID, active_pieces, error = game_manager.remove_piece(
                        params["piece_ID"], player_num)

                    # Generate a JSON response about the move's outcome
                    result = {"success": error == "",
                              "action": "remove_piece",
                              "error": error,
                              "next_player": game_manager.current_turn,
                              "next_state": game_manager.game_state.name,
                              "board_state": game_manager.board_state.tolist(),
                              "removed_piece": piece_ID,
                              "active_pieces": active_pieces}

                # MOVE PIECE CASE
                elif action == "move_piece":
                    # Check that the request contains all the required keys
                    required_keys = ("new_x", "new_y",
                                     "piece_ID")
                    if not all(key in params for key in required_keys):
                        print("Couldn't load all the necessary parameters")
                        continue

                    # Pass the player's action to the game manager
                    x, y, piece_ID, active_pieces, error = game_manager.move_piece(
                        params["new_x"], params["new_y"], params["piece_ID"], player_num)

                    # Generate a JSON response about the move's outcome
                    result = {"success": error == "",
                              "action": "move_piece",
                              "board_state": game_manager.board_state.tolist(),
                              "error": error,
                              "next_player": game_manager.current_turn,
                              "next_state": game_manager.game_state.name,
                              "moved_piece": piece_ID,
                              "new_x": x,
                              "new_y": y,
                              "active_pieces": active_pieces}

                # INVALID ACTION CASE
                else:
                    result = {
                        "success": False,
                        "error": "Invalid action"
                    }

                # Notify the player of the move's outcome
                await connection.send(json.dumps(result))

                # Notify the opponent if the move was successful and the opponent is on a different connection
                if result["success"] and connection != opponent:
                    await opponent.send(json.dumps(result))

                # Notify both players if the last move ended the game
                if result["next_state"] == GameState.STOPPED:
                    # Remove all references to the player websockets and the game manager
                    result = await close_connection(connection, EndFlags.PLAYER_WON)

                    await connection.send(json.dumps(result))

    except Exception as e:
        print("Connection closed: ", e)

        # Remove all references to the player websockets and the game manager
        await close_connection(connection, EndFlags.PLAYER_DISCONNECTED)


async def main():
    async with websockets.serve(handler, "0.0.0.0", 8765):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
