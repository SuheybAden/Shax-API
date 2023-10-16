import asyncio
import websockets
from websockets.server import WebSocketServerProtocol
import json
import secrets

from board_manager import BoardManager


# Game type (key) -> Player websocket(value)
game_types: dict[int, WebSocketServerProtocol] = {}

# dict of player websockets that are in the waiting list
waiting_list: dict[WebSocketServerProtocol, int] = {}

# BoardManager (key) -> List of Player Websockets (value)
games: dict[BoardManager, list[WebSocketServerProtocol, WebSocketServerProtocol]] = {}

# Player Websocket(key) -> List containing the BoardManager and opposing player (value)
players: dict[WebSocketServerProtocol, list[BoardManager, WebSocketServerProtocol]] = {}


# Takes in a new connection looking for a game.
# If the waiting list has another connection waiting for the same type of game,
# a new game is started between it and the new connection.
# Otherwise, the new connection is put into the waiting list
async def join_game(connection, params):
    # Load all the necessary parameters
    try:
        game_type: int = params["game_type"]
    except Exception:
        response = {
            "success": False,
            "error": "Wasn't given all the necessary parameters for joining a game",
        }
        await connection.send(json.dumps(response))
        return

    # Check if the connection is requesting for a local game
    is_local = (bool)((game_type & (1 << 0x0)) >> 0x0)

    # Check if there is another player in the waiting list who's waiting for the same type of game
    if game_type in game_types or is_local:
        # Generate random IDs for each player
        n = 1000
        p1_id = 1  # secrets.randbelow(n)
        p2_id = 2  # secrets.randbelow(n)

        game_params = {"min_pieces": 2, "max_pieces": 7,
                       "p1_id": p1_id, "p2_id": p2_id}

        # Start a new game
        game_manager: BoardManager = BoardManager(game_params)
        game_manager.start_game(game_params)

        # Loads the adjacent pieces array into a JSON-compatible format
        adjacent_pieces_json = {str(key): [(int(val1), int(val2)) for val1, val2 in value]
                                for key, value in game_manager.adjacent_pieces.items()}

        # Generate a default API response
        response = {
            "success": True,
            "waiting": False,
            "player1_key": p1_id,
            "player2_key": p2_id,
            "player_num": 0,
            "action": "join_game",
            "adjacent_pieces": adjacent_pieces_json
        }

        if is_local:
            opponent = connection
            await connection.send(json.dumps(response))

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
        players[connection] = (game_manager, opponent)
        players[opponent] = (game_manager, connection)

        return

    # Otherwise, add the new player to the waiting list
    else:
        game_types[game_type] = connection
        waiting_list[connection] = game_type

        print("waiting")
        response = {"success": True, "waiting": True, "action": "join_game", "adjacent_pieces": {}}
        await connection.send(json.dumps(response))
        return


# Remove any references to the player
async def close_connection(connection):
    # If they were in a game, remove any remaining references to the player and their opponent
    if connection in players:
        board_manager, opponent = players.pop(connection, None)

        # Generate defualt API response
        result = {"success": True,
                  "action": "end",
                  "won": True,
                  "msg": "Game Over"}

        # Check if it was a local game
        is_local = connection == opponent

        if not is_local:
            players.pop(opponent, None)

            # Tell the other player that their opponent left
            result["msg"] = "Opponent Forfeited."
            await opponent.send(json.dumps(result))

            # Generate message for telling the player that they forfeited
            result["won"] = False
            result["msg"] = "You Forfeited."

        return result

    # Remove any references to the disconnected player in the waiting list
    elif connection in waiting_list:
        game_type = waiting_list.pop(connection)
        game_types.pop(game_type)

        # Generate the message for telling the player that they left the waiting list
        result = {"success": True,
                  "action": "end",
                  "msg": "You've left the waiting list."}

        return result

    else:
        # Generate the message for telling the player that they left the waiting list
        result = {"success": False,
                  "error": "You are neither in a waiting list or game"}

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

            # END CASE
            elif action == "end":
                response = await close_connection(connection)

                print(response["msg"])

                # Notify the player that they have successfully quit
                response["action"] = action
                await connection.send(json.dumps(response))

            # SYMMETRICAL CASES
            else:
                game_manager, opponent = players.get(connection, None)

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
                    result = game_manager.place_piece(params)

                # REMOVE PIECE CASE
                elif action == "remove_piece":
                    result = game_manager.remove_piece(params)

                # MOVE PIECE CASE
                elif action == "move_piece":
                    result = game_manager.move_piece(params)

                # INVALID ACTION CASE
                else:
                    result = {
                        "success": False,
                        "error": "Invalid action"
                    }

                # Notify the player of the game's results
                await connection.send(json.dumps(result))

                # Notify the opponent if the move was successful
                if (result["success"]):
                    await opponent.send(json.dumps(result))

                # Notify both players if the last move ended the game
                if "game_over" in result:
                    result = game_manager.end_game()

                    # Tell the player who made the move that they won
                    await connection.send(json.dumps(result))

                    # Tell the other player that they lost
                    result["won"] = False
                    result["msg"] = "You Lost."
                    await opponent.send(json.dumps(result))

                    # Remove all references to the player websockets and the game manager
                    await close_connection(connection)

    except Exception as e:
        print("Connection closed: ", e)

        # Remove all references to the player websockets and the game manager
        await close_connection(connection)


async def main():
    async with websockets.serve(handler, "0.0.0.0", 8765):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
