import asyncio
import websockets
from websockets.server import WebSocketServerProtocol
import json
import secrets

from board_manager import BoardManager, GameState


# Game type (key) -> Player websocket(value)
game_types: dict = {}

# dict of player websockets that are in the waiting list
waiting_list: dict = {}

# BoardManager (key) -> List of Player Websockets (value)
games: dict = {}

# Player Websocket(key) -> List containing the BoardManager, opposing player, and the player's token (value)
players: dict = {}


# Takes in a new connection looking for a game.
# If the waiting list has another connection waiting for the same type of game,
# a new game is started between it and the new connection.
# Otherwise, the new connection is put into the waiting list
async def join_game(connection, params):
    # Generate a default API response
    response = {
        "success": True,
        "action": "join_game",
        "error": "",
        "waiting": False,
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
        response["success"] = False
        response["error"] = "Wasn't given all the necessary parameters for joining a game"
        await connection.send(json.dumps(response))
        return

    # Check if the connection is requesting for a local game
    is_local = (bool)((game_type & (1 << 0x0)) >> 0x0)

    # Check if there is either another player waiting for the same type of game or if this is a local game
    if game_type in game_types or is_local:
        # Generate random IDs for each player
        n = 1000
        p1_id = 1  # secrets.randbelow(n)
        p2_id = 2  # secrets.randbelow(n)

        # Start a new game
        game_manager: BoardManager = BoardManager(min_pieces=2, max_pieces=7)
        response["next_player"] = game_manager.start_game(
            p1_id=p1_id, p2_id=p2_id)
        response["next_state"] = game_manager.game_state.name

        # Loads the adjacent pieces array into a JSON-compatible format
        adjacent_pieces_json = []
        for node, neighbors in game_manager.adjacent_pieces.items():
            neighbors_array = []

            for neighbor in neighbors:
                neighbors_array.append({"x": neighbor[0], "y": neighbor[1]})

            adjacent_pieces_json.append({"x": node[0], "y": node[1], "neighbors": neighbors_array})
        response["adjacent_pieces"] = adjacent_pieces_json

        # Gives the connection both keys if both player are from the same source
        if is_local:
            opponent = connection

            response["player1_key"] = p1_id
            response["player2_key"] = p2_id
            await connection.send(json.dumps(response))

        # Otherwise, gives each connection their respective key
        else:
            # Finds the other player and removes them from the waiting list
            opponent = game_types.pop(game_type)
            waiting_list.pop(opponent)

            # Notify each player that a game was started
            # Give each of them their respective player keys
            response["player1_key"] = p1_id
            response["player2_key"] = 0
            await connection.send(json.dumps(response))

            response["player1_key"] = 0
            response["player2_key"] = p2_id
            response["player_num"] = 1
            await opponent.send(json.dumps(response))

        # Update all references
        games[game_manager] = (connection, opponent)
        players[connection] = (game_manager, opponent, 0)
        players[opponent] = (game_manager, connection, 1)

        return

    # Otherwise, add the new player to the waiting list
    game_types[game_type] = connection
    waiting_list[connection] = game_type

    print("waiting")
    response["waiting"] = True
    await connection.send(json.dumps(response))
    return


# Remove any references to the player
async def close_connection(connection):
    # Generate the defualt API response
    result = {"success": True,
                "action": "quit_game",
                "error": "",
                "forfeit": False,
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

    # Remove any references to the disconnected player in the waiting list
    elif connection in waiting_list:
        game_type = waiting_list.pop(connection)
        game_types.pop(game_type)

    else:
        # Generate the message for telling the player that they left the waiting list
        result["success"] = False
        result["error"] = "You are neither in a waiting list or game"

    return result


async def handler(connection):
    print("There's a new connection from ", connection.remote_address[0], "!")

    try:
        async for message in connection:
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
                    "error": "\"action\" property could not be found in the JSON request"
                }
                await connection.send(json.dumps(response))
                continue


            # START GAME CASE
            if action == "join_game":
                print("A player is trying to join a game")

                # Create the response template
                response = {
                    "success": False,
                    "action": "join_game"
                }

                # Checks if the player is already in a game
                if connection in players:
                    response["error"] = "The player is already in a game"
                    await connection.send(json.dumps(response))

                # Checks if the player is already waiting for a game
                elif connection in waiting_list:
                    response["error"] = "The player is already in the waiting list"
                    await connection.send(json.dumps(response))

                # Tries connecting a new player to a game
                else:
                    await join_game(connection, params)


            # QUIT GAME CASE
            elif action == "quit_game":
                response = await close_connection(connection)

                # Notify the player that they have successfully quit
                response["action"] = action
                await connection.send(json.dumps(response))


            # GAME RELATED CASES
            else:
                game_manager, opponent, player_num = players.get(connection, [None, None, None])

                # For local games, always set the player_num to the current turn
                if connection == opponent:
                    player_num = game_manager.current_turn

                # Check if the player is in a game
                if game_manager is None:
                    response = {
                        "success": False,
                        "action": action,
                        "error": "The player isn't in a game yet"
                    }
                    await connection.send(json.dumps(response))
                    continue


                # PLACE PIECE CASE
                if action == "place_piece":
                    print("placing")
                    # Check that the request contains all the required keys
                    required_keys = ("x", "y")
                    if not all(key in params for key in required_keys):
                        print("Couldn't load all the necessary parameters")
                        continue

                    new_ID, x, y, active_pieces, error = game_manager.place_piece(
                        params["x"], params["y"], player_num)

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
                    print("removing")
                    print("piece_ID" in params)
                    print(key in params for key in required_keys)
                    if not all(key in params for key in required_keys):
                        print("Couldn't load all the necessary parameters")
                        continue

                    piece_ID, game_over, active_pieces, error = game_manager.remove_piece(
                        params["piece_ID"], player_num)

                    result = {"success": error == "",
                              "action": "remove_piece",
                              "error": error,
                              "next_player": game_manager.current_turn,
                              "next_state": game_manager.game_state.name,
                              "board_state": game_manager.board_state.tolist(),
                              "game_over": game_over,
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

                    x, y, piece_ID, active_pieces, error = game_manager.move_piece(
                        params["new_x"], params["new_y"], params["piece_ID"], player_num)

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

                # Notify the player of the game's results
                await connection.send(json.dumps(result))

                # Notify the opponent if the move was successful and the game is remote
                if result["success"] and connection != opponent:
                    await opponent.send(json.dumps(result))

                # Notify both players if the last move ended the game
                if "game_over" in result and result["game_over"]:
                    # Remove all references to the player websockets and the game manager
                    result = await close_connection(connection)

                    await connection.send(json.dumps(result))

    except Exception as e:
        print("Connection closed: ", e)

        # Remove all references to the player websockets and the game manager
        await close_connection(connection)


async def main():
    async with websockets.serve(handler, "0.0.0.0", 8765):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
