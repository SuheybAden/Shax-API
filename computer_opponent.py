import sys
from board_manager import GameState
import numpy as np
from board_manager import BoardManager, GameState
import math
import asyncio
import websockets
import json
import subprocess


class ComputerOpponent():
    def __init__(self) -> None:
        pass

    def make_move(self, board_manager: BoardManager):
        _, best_move = self.minimax(3, -math.inf, math.inf,
                                    board_manager.current_turn == 1, board_manager)
        return best_move

    def minimax(self, depth, alpha, beta, maximizing_player, board_manager: BoardManager):
        # Save the current game variables
        current_turn = board_manager.current_turn
        board_state = np.copy(board_manager.board_state)
        total_pieces = np.copy(board_manager.total_pieces)
        first_to_jare = board_manager.first_to_jare
        current_jare = np.copy(board_manager.current_jare)
        game_state = board_manager.game_state

        # Check if the base case was reached
        if depth == 0 or game_state == GameState.STOPPED:
            return self.evaluate_game(board_manager), []

        # Computer's Turn
        if maximizing_player:
            maxEval = -math.inf
            bestMove = []

            # Placement Stage
            if (game_state == GameState.PLACEMENT):
                # Get all the empty spots on the board
                empty_spots = np.where(board_state == -1)

                # Place a piece on each spot and minimax the new board
                for i in range(len(empty_spots[0])):
                    spot = (empty_spots[1][i], empty_spots[0][i])
                    # print("\t"*(3-depth), "CPU places piece at", spot)
                    board_manager.place_piece(spot[0], spot[1], 1)

                    child_eval, _ = self.minimax(
                        depth - 1, alpha, beta, board_manager.current_turn == 1, board_manager)

                    # Reset the board to its previous state
                    board_manager.current_turn = current_turn
                    board_manager.board_state = np.copy(board_state)
                    board_manager.total_pieces = np.copy(total_pieces)
                    board_manager.first_to_jare = first_to_jare
                    board_manager.current_jare = np.copy(current_jare)
                    board_manager.game_state = game_state

                    # Check if this is the best move yet
                    if (child_eval > maxEval):
                        maxEval = child_eval
                        bestMove = [spot[0], spot[1]]

                    # Prune options
                    alpha = max(alpha, child_eval)
                    if beta <= alpha:
                        break

                return maxEval, bestMove

            # Removal Stage
            elif (game_state == GameState.REMOVAL or game_state == GameState.FIRST_REMOVAL):
                # Get the indices of all the human player's pieces
                # TODO: check if there is a better way to do this
                board_copy = np.copy(board_state)
                non_null = np.logical_and(board_copy != None, board_copy != -1)
                board_copy[non_null] = board_copy[non_null] & 1
                indices = np.where(board_copy == 0)

                # Remove each piece and minimax the new board
                for i in range(len(indices[0])):
                    x = indices[1][i]
                    y = indices[0][i]
                    id = board_state[y][x]

                    # print("\t"*(3-depth), "CPU removes piece", id)
                    board_manager.remove_piece(id, 1)
                    child_eval, _ = self.minimax(
                        depth - 1, alpha, beta, board_manager.current_turn == 1, board_manager)

                    # Reset the board to its previous state
                    board_manager.current_turn = current_turn
                    board_manager.board_state = np.copy(board_state)
                    board_manager.total_pieces = np.copy(total_pieces)
                    board_manager.first_to_jare = first_to_jare
                    board_manager.current_jare = np.copy(current_jare)
                    board_manager.game_state = game_state

                    # Check if this is the best move yet
                    if (child_eval > maxEval):
                        maxEval = child_eval
                        bestMove = [id]

                    # Prune options
                    alpha = max(alpha, child_eval)
                    if beta <= alpha:
                        break

                return maxEval, bestMove

            # Movement State
            elif (game_state == GameState.MOVEMENT):
                # Get the indices of all the computer's pieces
                # TODO: check if there is a better way to do this
                board_copy = np.copy(board_state)
                non_null = np.logical_and(board_copy != None, board_copy != -1)
                board_copy[non_null] = board_copy[non_null] & 1
                indices = np.where(board_copy == 1)

                # Move each piece and minimax the new board
                for i in range(len(indices[0])):
                    x = indices[1][i]
                    y = indices[0][i]
                    id = board_state[y][x]

                    possible_moves = board_manager._get_possible_moves(id)
                    for move in possible_moves:

                        # print("\t"*(3-depth), "CPU moves piece", id, "to", move)
                        board_manager.move_piece(move[0], move[1], id, 1)

                        child_eval, _ = self.minimax(
                            depth - 1, alpha, beta, board_manager.current_turn == 1, board_manager)

                        # Reset the board to its previous state
                        board_manager.current_turn = current_turn
                        board_manager.board_state = np.copy(board_state)
                        board_manager.total_pieces = np.copy(total_pieces)
                        board_manager.first_to_jare = first_to_jare
                        board_manager.current_jare = np.copy(current_jare)
                        board_manager.game_state = game_state

                        # Check if this is the best move yet
                        if (child_eval > maxEval):
                            maxEval = child_eval
                            bestMove = [move[0], move[1], id]

                        # Prune options
                        alpha = max(alpha, child_eval)
                        if beta <= alpha:
                            break

                return maxEval, bestMove

        # Player's turn
        else:
            minEval = math.inf
            bestMove = []

            # Placement Stage
            if (game_state == GameState.PLACEMENT):
                # Get all the empty spots on the board
                empty_spots = np.where(board_state == -1)

                # Place a piece on each spot and minimax the new board
                for i in range(len(empty_spots[0])):
                    spot = (empty_spots[1][i], empty_spots[0][i])
                    # print("\t"*(3-depth), "Player places piece at", spot)
                    board_manager.place_piece(spot[0], spot[1], 0)

                    child_eval, _ = self.minimax(
                        depth - 1, alpha, beta, board_manager.current_turn == 1, board_manager)

                    # Reset the board to its previous state
                    board_manager.current_turn = current_turn
                    board_manager.board_state = np.copy(board_state)
                    board_manager.total_pieces = np.copy(total_pieces)
                    board_manager.first_to_jare = first_to_jare
                    board_manager.current_jare = np.copy(current_jare)
                    board_manager.game_state = game_state

                    # Check if this is the best move yet
                    if (child_eval < minEval):
                        minEval = child_eval
                        bestMove = [spot[0], spot[1]]

                    # Perform pruning
                    beta = min(beta, child_eval)
                    if beta <= alpha:
                        break

                return minEval, bestMove

            # Removal Stage
            elif (game_state == GameState.REMOVAL or game_state == GameState.FIRST_REMOVAL):
                # Get the indices of all the computer's pieces
                # TODO: check if there is a better way to do this
                board_copy = np.copy(board_state)
                non_null = np.logical_and(board_copy != None, board_copy != -1)
                board_copy[non_null] = board_copy[non_null] & 1
                indices = np.where(board_copy == 1)

                # Remove each piece and minimax the new board
                for i in range(len(indices[0])):
                    x = indices[1][i]
                    y = indices[0][i]
                    id = board_state[y][x]

                    # print("\t"*(3-depth), "Player removes piece", id)
                    board_manager.remove_piece(id, 0)

                    child_eval, _ = self.minimax(
                        depth - 1, alpha, beta, board_manager.current_turn == 1, board_manager)

                    # Reset the board to its previous state
                    board_manager.current_turn = current_turn
                    board_manager.board_state = np.copy(board_state)
                    board_manager.total_pieces = np.copy(total_pieces)
                    board_manager.first_to_jare = first_to_jare
                    board_manager.current_jare = np.copy(current_jare)
                    board_manager.game_state = game_state

                    # Check if this is the best move yet
                    if (child_eval < minEval):
                        minEval = child_eval
                        bestMove = [id]

                    # Perform pruning
                    beta = min(beta, child_eval)
                    if beta <= alpha:
                        break

                return minEval, bestMove

            # Movement State
            elif (game_state == GameState.MOVEMENT):
                # Get the indices of all the human player's pieces
                # TODO: check if there is a better way to do this
                board_copy = np.copy(board_state)
                non_null = np.logical_and(board_copy != None, board_copy != -1)
                board_copy[non_null] = board_copy[non_null] & 1
                indices = np.where(board_copy == 0)

                # Move each piece and minimax the new board
                for i in range(len(indices[0])):
                    x = indices[1][i]
                    y = indices[0][i]
                    id = board_state[y][x]

                    possible_moves = board_manager._get_possible_moves(id)
                    for move in possible_moves:

                        # print("\t"*(3-depth), "Player moves piece", id, "to", move)
                        board_manager.move_piece(move[0], move[1], id, 0)

                        child_eval, _ = self.minimax(
                            depth - 1, alpha, beta, board_manager.current_turn == 1, board_manager)

                        # Reset the board to its previous state
                        board_manager.current_turn = current_turn
                        board_manager.board_state = np.copy(board_state)
                        board_manager.total_pieces = np.copy(total_pieces)
                        board_manager.first_to_jare = first_to_jare
                        board_manager.current_jare = np.copy(current_jare)
                        board_manager.game_state = game_state

                        # Check if this is the best move yet
                        if (child_eval < minEval):
                            minEval = child_eval
                            bestMove = [move[0], move[1], id]

                        beta = min(beta, child_eval)
                        if beta <= alpha:
                            break

                return minEval, bestMove

    # Evaluate the value of the board
    # TODO: Find a better metric for a good vs. bad board
    def evaluate_game(self, board_manager: BoardManager):
        player_pieces, comp_pieces = board_manager.total_pieces

        return comp_pieces - player_pieces


# TODO: Implement this function
def update_board(board_manager: BoardManager, response: dict):
    print(response)

    # # Increment the total number of pieces if a piece is placed
    # if (response["action"] == "place_piece"):
    #     board_manager.total_pieces[board_manager.current_turn] += 1

    # board_manager.current_turn = response["next_player"]
    # board_manager.board_state = np.array(response["board_state"])
    # board_manager.first_to_jare =
    # board_manager.current_jare =
    # board_manager.game_state =

    # Handle updating the game after each move
    if (response["action"] == "place_piece"):
        _, _, _, _, error = board_manager.place_piece(
            response["new_x"], response["new_y"], board_manager.current_turn)
    elif (response["action"] == "remove_piece"):
        _, _, error = board_manager.remove_piece(
            response["removed_piece"], board_manager.current_turn)
    elif (response["action"] == "move_piece"):
        _, _, _, _, error = board_manager.move_piece(
            response["new_x"], response["new_y"], response["moved_piece"], board_manager.current_turn)
    else:
        print("The board manager is in an unknown game state")
        return

    if error != "":
        print("Failed to update the board")
        print("Error: " + error)


async def play_with_bot(uri: str, game_type: int):
    async with websockets.connect(uri) as ws:
        player_num = 0
        cpu = ComputerOpponent()
        board_manager: BoardManager = BoardManager(2, 12)

        # Join the game the player's in
        response = {"action": "join_game",
                       "game_type": game_type}
        await ws.send(json.dumps(response))

        # Check if the bot couldn't join the game
        print("CPU: Trying to join the lobby")
        raw_msg = await ws.recv()
        message = json.loads(raw_msg)
        if not message["success"] or message["waiting"]:
            print("Failed to join the private lobby. Please double check your lobby key")

        is_game_running = True
        board_manager.start_game()
        # Process each game action until the game ends
        while is_game_running:
            print("in loop")
            print(type(board_manager))
            # Shutdown the CPU if the game has ended
            if board_manager.game_state.name == "STOPPED":
                # Wait for the final close_connection message before exiting the loop
                await ws.recv()
                return

            # If the other player goes next, just wait for the outcome of their move
            if (board_manager.current_turn != player_num):
                pass

            else:
                # Otherwise, calculate the best move the cpu can make
                best_move = cpu.make_move(board_manager)

                print(board_manager.game_state.name)

                # Send the best move over to the API
                if board_manager.game_state.name == "PLACEMENT":
                    print("The CPU is placing a piece.\n")
                    response = {"action": "place_piece",
                                "x": int(best_move[0]),
                                "y": int(best_move[1])}
                    await ws.send(json.dumps(response))

                    print("CPU attempted to place piece at:",
                        int(best_move[0]), int(best_move[1]))

                elif board_manager.game_state.name == "REMOVAL" or board_manager.game_state.name == "FIRST_REMOVAL":
                    print("The CPU is removing a piece.\n")
                    response = {"action": "remove_piece",
                                "piece_ID": best_move[0]}
                    await ws.send(json.dumps(response))

                elif board_manager.game_state.name == "MOVEMENT":
                    print("The CPU is moving a piece.\n")
                    response = {"action": "move_piece",
                                "new_x": best_move[0],
                                "new_y": best_move[1],
                                "piece_ID": best_move[2]}
                    await ws.send(json.dumps(response))

            # Wait for the result of the previous move
            raw_response = await ws.recv()
            response = json.loads(raw_response)

            # Check if the previous move FAILED
            # *** THIS SHOULD NEVER HAPPEN ***
            # The cpu should only be playing legal moves and
            # the API only returns the opposing player's move if it succeeded
            if not response["success"]:
                print("*** ILLEGAL MOVE: SOMETHING WENT WRONG")

            if response["action"] == "quit_game":
                print("Shutting down the CPU opponent")
                return

            # Update the board based on the results of the previous turn
            update_board(board_manager, response)

            # Add a delay so the move's aren't instantaneous
            await asyncio.sleep(1)


# MAIN LOOP
if __name__ == "__main__":
    print("Creating a new CPU opponent")

    uri = "ws://" + sys.argv[2] + ":" + sys.argv[3]
    asyncio.run(play_with_bot(uri, int(sys.argv[1])))
