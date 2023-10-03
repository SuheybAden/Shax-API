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
players: dict[WebSocketServerProtocol, list[BoardManager,WebSocketServerProtocol]] = {}


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
        p1_id = secrets.randbelow(n)
        p2_id = secrets.randbelow(n)

        game_params = {"min_pieces": 2, "max_pieces": 7,
                       "p1_id": p1_id, "p2_id": p2_id}

        # Add both players to a new game
        game_manager = BoardManager(game_params)
        game_manager.start_game(game_params)

        # Update all references
        games[game_manager] = (connection, opponent)
        players[connection] = (game_manager, opponent)
        players[opponent] = (game_manager, connection)

        response = {
            "success": True,
            "waiting": False,
            "id": p1_id,
            "action": "join_game",
            "board_state": game_manager.board_state.tolist(),
        }
        await connection.send(json.dumps(response))

        response["id"] = p2_id
        await opponent.send(json.dumps(response))
        return

    # Otherwise, add the new player to the waiting list
    else:
        game_types[game_type] = connection
        waiting_list[connection] = game_type

        response = {"success": True, "waiting": True, "action": "join_game"}
        await connection.send(json.dumps(response))
        return


async def close_connection(connection):
    # If the disconnected player was in a game, conclude the game they were in
    if connection in players:
        board_manager, opponent = players.pop(connection)

        # Tell the other player that their opponent left
        response = {"success": True,
                    "game_over": True,
                    "msg": "Your opponent has forfeited."}
        await opponent.send(json.dumps(response))

        # Remove any remaining references to the other player
        players.pop(opponent, None)

    # Otherwise, remove any references to the disconnected player in the waiting list
    elif connection in waiting_list:
        game_type = waiting_list.pop(connection)
        game_types.pop(game_type)


async def handler(connection):
    print("There's a new connection!")

    try:
        async for message in connection:
            params = json.loads(message)

            # FOR TESTING PURPOSES
            if "test" in params:
                await connection.send(json.dumps({}))
                continue

            # Load all the necessary parameters for this step
            try:
                action: str = params["action"]
            except Exception:
                response = {
                    "success": False,
                    "error": "JSON object isn't formatted properly"
                }
                await connection.send(json.dumps(response))
                continue

            # START GAME CASE
            if action == "join_game":
                # Checks if the player is already in a game
                if connection in players:
                    response = {
                        "success": False,
                        "action": "join_game",
                        "error": "The player is already in a game"
                    }
                    await connection.send(json.dumps(response))

                # Checks if the player is already waiting for a game
                elif connection in waiting_list:
                    response = {
                        "success": False,
                        "action": "join_game",
                        "error": "The player is already in the waiting list"
                    }
                    await connection.send(json.dumps(response))

                # Tries connecting a new player to a game
                else:
                    await join_game(connection, params)

            # PLACE PIECE CASE
            elif action == "place_piece":
                game_manager, opponent = players.get(connection, None)

                # Checks if the player is in a game
                if game_manager is None:
                    response = {
                        "success": False,
                        "action": "place_piece",
                        "error": "The player isn't in a game yet"
                    }
                    await connection.send(json.dumps(response))
                    continue

                # Passes the move to the game manager and sends back the outcome
                result = game_manager.place_piece(params)
                await connection.send(json.dumps(result))

                # Notify the opponent if the move was successful
                if(result["success"]):
                    await opponent.send(json.dumps(result))

            # REMOVE PIECE CASE
            elif action == "remove_piece":
                game_manager = players.get(connection, None)

                # Checks if the player is in a game
                if game_manager is None:
                    response = {
                        "success": False,
                        "action": "remove_piece",
                        "error": "The player isn't in a game yet"
                    }
                    await connection.send(json.dumps(response))
                    continue

                # Passes the move to the game manager and sends back the outcome
                result = game_manager.remove_piece(params)
                await connection.send(json.dumps(result))
                
                # Notify the opponent if the move was successful
                if(result["success"]):
                    await opponent.send(json.dumps(result))

            # MOVE PIECE CASE
            elif action == "move_piece":
                game_manager = players.get(connection, None)

                # Checks if the player is in a game
                if game_manager is None:
                    response = {
                        "success": False,
                        "action": "move_piece",
                        "error": "The player isn't in a game yet"
                    }
                    await connection.send(json.dumps(response))
                    continue

                # Passes the move to the game manager and sends back the outcome
                result = game_manager.move_piece(params)
                await connection.send(json.dumps(result))

                # Notify the opponent if the move was successful
                if(result["success"]):
                    await opponent.send(json.dumps(result))

            # FORFEIT CASE
            elif action == "forfeit":
                game_manager = players.get(connection, None)

                # Checks if the player is in a game
                if game_manager is None:
                    response = {
                        "success": False,
                        "action": "forfeit",
                        "error": "The player isn't in a game yet"
                    }
                    await connection.send(json.dumps(response))
                    continue

                # Passes the move to the game manager and sends back the outcome
                # TODO: uncomment the lines below once the forfeit function has been implemented
                result = game_manager.end_game()
                await connection.send(json.dumps(result))

                # Notify the opponent if the move was successful
                if(result["success"]):
                    await opponent.send(json.dumps(result))

            # INVALID ACTION CASE
            else:
                response = {
                            "success": False,
                            "error": "Invalid action"
                            }
                await connection.send(json.dumps(response))

    except Exception:
        print("Connection closed.")
        await close_connection(connection)


async def main():
    async with websockets.serve(handler, "0.0.0.0", 8765):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
