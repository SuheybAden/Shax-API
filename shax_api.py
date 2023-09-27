import asyncio
import websockets
from websockets.server import WebSocketServerProtocol
import json
import secrets

from board_manager import BoardManager


# Game type (key) -> Player websocket(value)
waiting_list: dict[int, WebSocketServerProtocol] = {}

# BoardManager (key) -> List of Player Websockets (value)
games: dict[BoardManager, WebSocketServerProtocol] = {}

# Player Websocket(key) -> BoardManager (value)
players: dict[WebSocketServerProtocol, BoardManager] = {}

# List of connected player websockets
connected: list[WebSocketServerProtocol] = []


async def join_game(connection, params):
    # Load all the necessary parameters
    try:
        game_type = params["game_type"]
    except Exception:
        response = {
            "success": False,
            "error": "Wasn't given all the necessary parameters for joining a game",
        }
        await connection.send(json.dumps(response))
        return

    # Add this new connection to the list of known connections
    connected.append(connection)

    # Check if there is another player in the waiting list who's waiting for the same game
    opponent = waiting_list.pop(game_type, None)

    if opponent is not None and opponent != connection:
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
        players[connection] = game_manager
        players[opponent] = game_manager

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

    else:
        waiting_list[game_type] = connection
        response = {"success": True, "waiting": True, "action": "join_game"}
        await connection.send(json.dumps(response))


async def close_connection(connection, unexpected):
    board_manager = players.pop(connection, None)

    if board_manager is not None:
        connections = games.pop(board_manager)

        # Give a final message to each player and close their connections
        for c in connections:
            if c == connection and unexpected:
                continue
            else:
                response = {"success": True,
                            "game_over": True, "msg": "Game Over"}
                await c.send(json.dumps(response))

            # Remove any remaining references to the players
            try:
                players.pop(c, None)
                connected.remove(c)
            except Exception:
                pass


async def handler(connection):
    print("There's a new connection!")

    try:
        async for message in connection:
            # Load all the necessary parameters for this step
            try:
                params = json.loads(message)
                action = params["action"]
            except Exception:
                response = {
                    "success": False,
                    "error": "JSON object isn't formatted properly",
                }
                await connection.send(json.dumps(response))
                continue

            if action == "start_game":
                # Checks if the player is already in a game
                if connection in players:
                    response = {
                        "success": False,
                        "action": "start_game",
                        "error": "The player is already in a game",
                        "result": "in_game",
                    }
                    await connection.send(json.dumps(response))

                # Checks if the player is already connected
                elif connection in connected:
                    response = {
                        "success": False,
                        "action": "start_game",
                        "error": "The player is already in the waiting list",
                        "result": "waiting",
                    }
                    await connection.send(json.dumps(response))

                # Tries connecting a new player to a game
                else:
                    await join_game(connection, params)

            elif action == "place_piece":
                game_manager = players.get(connection, None)

                # Checks if the player is in a game
                if game_manager is None:
                    response = {
                        "success": False,
                        "action": "place_piece",
                        "error": "The player isn't in a game yet",
                        "result": "waiting",
                    }
                    await connection.send(json.dumps(response))
                    continue

                # Passes the move to the game manager and sends back the outcome
                result = game_manager.place_piece(params)
                await connection.send(json.dumps(result))

            elif action == "remove_piece":
                game_manager = players.get(connection, None)

                # Checks if the player is in a game
                if game_manager is None:
                    response = {
                        "success": False,
                        "action": "remove_piece",
                        "error": "The player isn't in a game yet",
                        "result": "waiting",
                    }
                    await connection.send(json.dumps(response))
                    continue

                # Passes the move to the game manager and sends back the outcome
                result = game_manager.remove_piece(params)
                await connection.send(json.dumps(result))

            elif action == "move_piece":
                game_manager = players.get(connection, None)

                # Checks if the player is in a game
                if game_manager is None:
                    response = {
                        "success": False,
                        "action": "move_piece",
                        "error": "The player isn't in a game yet",
                        "result": "waiting",
                    }
                    await connection.send(json.dumps(response))
                    continue

                # Passes the move to the game manager and sends back the outcome
                result = game_manager.move_piece(params)
                await connection.send(json.dumps(result))

            elif action == "forfeit":
                game_manager = players.get(connection, None)

                # Checks if the player is in a game
                if game_manager is None:
                    response = {
                        "success": False,
                        "action": "forfeit",
                        "error": "The player isn't in a game yet",
                        "result": "waiting",
                    }
                    await connection.send(json.dumps(response))
                    continue

                # Passes the move to the game manager and sends back the outcome
                # TODO: uncomment the lines below once the forfeit function has been implemented
                # result = game_manager.forfeit(params)
                # await connection.send(json.dumps(result))

            else:
                response = {"success": False, "error": "Invalid action"}
                await connection.send(json.dumps(response))
    except Exception:
        print("Connection ended")
        await close_connection(connection, True)

    finally:
        print("finally")
        await close_connection(connection, False)


async def main():
    async with websockets.serve(handler, "0.0.0.0", 8765):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
