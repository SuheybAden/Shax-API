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

    # Check if there is another player in the waiting list who's waiting for the same type of game
    if game_type in game_types:
        opponent = game_types.pop(game_type)

        # Remove the other player from the waiting list
        waiting_list.pop(opponent)

        # Generate random IDs for each player
        n = 1000
        p1_id = 1  # secrets.randbelow(n)
        p2_id = 2  # secrets.randbelow(n)

        game_params = {"min_pieces": 2, "max_pieces": 7,
                       "p1_id": p1_id, "p2_id": p2_id}

        # Add both players to a new game
        game_manager: BoardManager = BoardManager(game_params)
        game_manager.start_game(game_params)

        # Update all references
        games[game_manager] = (connection, opponent)
        players[connection] = (game_manager, opponent)
        players[opponent] = (game_manager, connection)

        adjacent_pieces_json = {str(key): [(int(val1), int(val2)) for val1, val2 in value]
                                for key, value in game_manager.adjacent_pieces.items()}
        response = {
            "success": True,
            "waiting": False,
            "player_ID": p1_id,
            "player_num": 0,
            "action": "join_game",
            "adjacent_pieces": adjacent_pieces_json
        }
        await connection.send(json.dumps(response))

        response["player_ID"] = p2_id
        response["player_num"] = 1
        await opponent.send(json.dumps(response))
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
        players.pop(opponent, None)

        # Tell the other player that their opponent left
        result = {"success": True,
                  "action": "end",
                  "won": True,
                  "msg": "Opponent Forfeited."}
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
                  "msg": "You are neither in a waiting list or game"}

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
