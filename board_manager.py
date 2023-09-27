from enum import Enum
import numpy as np

# Enum for tracking what state the game is in
# TODO: Come up with a better name for the 'MOVEMENT' game state


class GameState(Enum):
    STOPPED = 0
    PLACEMENT = 1
    FIRST_REMOVAL = 2
    REMOVAL = 3
    MOVEMENT = 4


class BoardManager:
    # Constructor function
    # Sets all the constant variables for the game
    def __init__(self, params) -> None:
        default_error_msg = "An error occured while initializing the board manager"

        # Load all the necessary input parameters
        try:
            # Minimum number of pieces a player can have or its game over
            self.MIN_PIECES = params["min_pieces"]

            # Maximum number of pieces each player can have
            self.MAX_PIECES = params["max_pieces"]

        except:
            return {"success": False,
                    "error": "Couldn't load all the necessary parameters"}

        # Total number of players
        self.TOTAL_PLAYERS = 2

        # How far of a piece can be from the center of its new location
        # Goes from 0 to 1
        self.MARGIN_OF_ERROR = .2

        # How far the pieces' ID needs to bit shifted to the left to store the player ID with it
        self.ID_SHIFT = 2

        # Adjacency list for keeping track of all the nodes the pieces can be placed in
        # TODO: find a better word than "nodes" and maybe rename this variable
        self.adjacent_pieces = {  # Outer Square Nodes
            (0, 0): [(0, 3), (3, 0)],
            (0, 3): [(0, 0), (1, 3), (0, 6)],
            (0, 6): [(0, 3), (3, 6)],
            (3, 6): [(0, 6), (3, 5), (6, 6)],
            (6, 6): [(3, 6), (6, 3)],
            (6, 3): [(6, 6), (5, 3), (6, 0)],
            (6, 0): [(6, 3), (3, 0)],
            (3, 0): [(6, 0), (3, 1), (0, 0)],

            (1, 1): [(1, 3), (3, 1)],
            (1, 3): [(1, 1), (2, 3), (0, 3), (1, 5)],
            (1, 5): [(1, 3), (3, 5)],
            (3, 5): [(1, 5), (3, 4), (3, 6), (5, 5)],
            (5, 5): [(3, 5), (5, 3)],
            (5, 3): [(5, 5), (4, 3), (6, 3), (5, 1)],
            (5, 1): [(5, 3), (3, 1)],
            (3, 1): [(5, 1), (3, 2), (3, 0), (1, 1)],

            (2, 2): [(3, 2), (2, 3)],
            (2, 3): [(2, 2), (1, 3), (2, 4)],
            (2, 4): [(2, 3), (3, 4)],
            (3, 4): [(2, 4), (3, 5), (4, 4)],
            (4, 4): [(3, 4), (4, 3)],
            (4, 3): [(4, 4), (5, 3), (4, 2)],
            (4, 2): [(4, 3), (3, 2)],
            (3, 2): [(4, 2), (3, 1), (2, 2)],
        }

    # Starts a game between two players
    # Initializes all the variables that keep track of the state of the game

    def start_game(self, params):
        # Load all the necessary input parameters
        try:
            self.players = []
            self.players.append(params["p1_id"])
            self.players.append(params["p2_id"])

        except:
            return {"success": False,
                    "error": "Couldn't load all the necessary parameters"}

        # Set which player goes first
        self.current_turn = 0

        # Load the starting state of the board
        self.board_size = 7
        self.board_state = np.array([[-1,     None,    None,    -1,      None,    None,    -1],
                                     [None,   -1,      None,    -1,      None,    -1,      None],
                                     [None,   None,    -1,      -1,      -1,      None,    None],
                                     [-1,     -1,      -1,      None,    -1,      -1,      -1],
                                     [None,   None,    -1,      -1,      -1,      None,    None],
                                     [None,   -1,      None,    -1,      None,    -1,      None],
                                     [-1,     None,    None,    -1,      None,    None,    -1]])

        # Array for keeping track of how many pieces each player has
        self.total_pieces = np.zeros(self.TOTAL_PLAYERS, np.int8)

        # Tracks the ID of the player who first made a jare in the placement stage
        # Determines which player goes first in the "first_removal" stage
        self.first_to_jare = None

        # Array containing the total number of "jare" each player has made
        self.current_jare = np.zeros(self.TOTAL_PLAYERS, np.int8)

        # Start the game off in the placement stage
        self.game_state = GameState.PLACEMENT

        self.game_running = True

    # Places a piece on the board

    def place_piece(self, params):
        # Checks if the game is in the placement stage yet
        if self.game_state != GameState.PLACEMENT:
            return {"success": False,
                    "board_state": self.board_state.tolist(),
                    "error": "The game is not in the placement stage",
                    "current_state": self.game_state.name}

        # Load all the necessary input parameters
        try:
            x = params["x"]
            y = params["y"]
            player = params["player"]

        except:
            return {"success": False,
                    "error": "Couldn't load all the necessary parameters"}

        # Checks if it's the player's turn
        if player != self.players[self.current_turn]:
            return {"success": False,
                    "action": "place_piece",
                    "board_state": self.board_state.tolist(),
                    "error": "It's not the player's turn yet",
                    "new_piece_id": new_ID,
                    "new_x": x,
                    "new_y": y,
                    "current_turn": self.current_turn,
                    "next_state": next_state}

        # Check if the piece is being played in a valid spot
        valid_spot = self._is_valid_spot(x, y)

        if valid_spot == None:
            return {"success": False,
                    "action": "place_piece",
                    "board_state": self.board_state.tolist(),
                    "error": "The current placement is at an invalid spot",
                    "new_piece_id": new_ID,
                    "new_x": x,
                    "new_y": y,
                    "current_turn": self.current_turn,
                    "next_state": next_state}

        # Generate an ID for the new game piece
        new_ID = (self.total_pieces[self.current_turn] << self.ID_SHIFT) | self.current_turn

        # Update the board's state with the new game piece
        self.board_state[y][x] = new_ID

        # Update the player's total number of pieces
        self.total_pieces[self.current_turn] += 1

        # Check if the first jare has been made yet
        if self._made_new_jare() and self.first_to_jare == None:
            self.first_to_jare = self.current_turn

        # Go to the next player's turn
        self.current_turn = (self.current_turn + 1) % self.TOTAL_PLAYERS

        # If all the pieces have been placed,
        # go on to the first removal state of the game
        if np.all(self.total_pieces >= self.MAX_PIECES):
            if self.first_to_jare != None:
                self.current_turn = self.first_to_jare

            # If no one made a jare in the placement stage, player 2 goes first
            else:
                self.current_turn = 1

            next_state = "removal"

        else:
            next_state = "placement"

        return {"success": True,
                "action": "place_piece",
                "board_state": self.board_state.tolist(),
                "error": None,
                "new_piece_id": new_ID,
                "new_x": x,
                "new_y": y,
                "current_turn": self.current_turn,
                "next_state": next_state}

    # Removes a game piece from the board
    def remove_piece(self, params):
        # Checks if the game is in one of the removal stages yet
        if self.game_state != GameState.REMOVAL or self.game_state != GameState.FIRST_REMOVAL:
            return {"success": False,
                    "board_state": self.board_state.tolist(),
                    "error": "The game is not in the removal stage",
                    "current_state": self.game_state.name}

        # Load all the necessary input parameters
        try:
            piece_ID = params["piece_ID"]
            player = params["player"]
        except Exception:
            return {"success": False,
                    "error": "Couldn't load all the necessary parameters"}

        # Checks if it's not the player's turn yet
        if player != self.players[self.current_turn]:
            return {"success": False,
                    "action": "remove_piece",
                    "board_state": self.board_state.tolist(),
                    "error": "It's not the player's turn yet",
                    "current_turn": self.current_turn}

        # Checks if the piece exists
        if piece_ID not in self.board_state:
            return {"success": False,
                    "action": "remove_piece",
                    "board_state": self.board_state.tolist(),
                    "error": "The piece to be removed doesn't exist",
                    "removed_piece": piece_ID,
                    "current_turn": self.current_turn}

        # Checks if the piece belongs to the current player
        piece_owner = piece_ID & (2**self.ID_SHIFT - 1)

        if piece_owner == self.current_turn:
            return {"success": False,
                    "action": "remove_piece",
                    "board_state": self.board_state.tolist(),
                    "error": "The piece belongs to the current player",
                    "current_turn": self.current_turn}

        # Remove the piece from the board
        self.board_state[self.board_state == piece_ID] = -1

        # Update the remaining pieces of the other player
        self.total_pieces[piece_owner] -= 1

        # End the game if one of the players won
        if (self._is_game_over()):
            self.game_state = GameState.STOPPED
            return {"success": True,
                    "action": "remove_piece",
                    "board_state": self.board_state.tolist(),
                    "error": None,
                    "removed_piece": piece_ID,
                    "next_state": "end_game"}

        active_pieces = []
        next_state = "removal"

        # If this is the very first removal stage,
        # every player must have a chance to remove a piece before going on to the movement stage
        # TODO: combine these conditions better
        if self.game_state == GameState.FIRST_REMOVAL:
            self.current_turn = (self.current_turn + 1) % self.TOTAL_PLAYERS

            if (self.first_to_jare is None and self.current_turn == 1) or \
                    (self.current_turn == self.first_to_jare):
                self.game_state = GameState.MOVEMENT
                next_state = "movement"
                active_pieces = self._get_active_pieces()

        else:
            self.game_state(GameState.MOVEMENT)
            next_state = "movement"
            active_pieces = self._get_active_pieces()

        return {"success": True,
                "action": "remove_piece",
                "board_state": self.board_state.tolist(),
                "error": None,
                "removed_piece": piece_ID,
                "active_pieces": active_pieces,
                "current_turn": self.current_turn,
                "next_state": next_state}

    # Moves a game piece from one spot to another
    def move_piece(self, params):
        # Checks if the game is in the movement stage
        if self.game_state != GameState.MOVEMENT:
            return {"success": False,
                    "action": "move_piece",
                    "error": "The game is not in the movement stage",
                    "board_state": self.board_state.tolist(),
                    "current_turn": self.current_turn,
                    "next_state": "move_piece"}

        # Load all the necessary input parameters
        try:
            x = params["x"]
            y = params["y"]
            piece_ID = params["piece_ID"]
            player = params["player"]

        except Exception:
            return {"success": False,
                    "error": "Couldn't load all the necessary parameters"}

        # Checks if it's the player's turn
        if player != self.players[self.current_turn]:
            return {"success": False,
                    "action": "move_piece",
                    "board_state": self.board_state.tolist(),
                    "error": "It's not the player's turn yet",
                    "moved_piece": piece_ID,
                    "new_x": x,
                    "new_y": y,
                    "current_turn": self.current_turn,
                    "next_state": "move_piece"}

        # Checks if the new coordinates are a valid spot on the board
        valid_spot = self._is_valid_spot(x, y)

        if valid_spot is None:
            return {"success": False,
                    "action": "move_piece",
                    "board_state": self.board_state.tolist(),
                    "error": "The piece was moved to an invalid spot",
                    "moved_piece": piece_ID,
                    "new_x": x,
                    "new_y": y,
                    "current_turn": self.current_turn,
                    "next_state": "move_piece"}

        # Get the old coordinates of the game piece
        old_x, old_y = self._piece_ID_to_coord(piece_ID)

        # Check if the new spot is adjacent to the old spot
        is_adjacent = valid_spot in self.adjacent_pieces[(old_x, old_y)]

        if not is_adjacent:
            return {"success": False,
                    "action": "move_piece",
                    "board_state": self.board_state.tolist(),
                    "error": "The piece was moved to a nonadjacent spot",
                    "moved_piece": piece_ID,
                    "new_x": x,
                    "new_y": y,
                    "current_turn": self.current_turn,
                    "next_state": "move_piece"}

        # Update the board's state
        self.board_state[old_y][old_x] = -1
        self.board_state[valid_spot[1]][valid_spot[0]] = piece_ID

        new_jare = self._made_new_jare()
        next_state = ""

        # Lets the current player go to the removal state if they made a new jare
        if new_jare:
            self.game_state = GameState.REMOVAL
            next_state = "removal"

        # Go on to the next player if no jare was made
        else:
            self.current_turn = (self.current_turn + 1) % self.TOTAL_PLAYERS
            next_state = "movement"

            # Checks if the next player has any pieces that can be moved
            active_pieces = self._get_active_pieces()

            if not active_pieces:
                print("Player " + str(self.current_turn + 1) + " can't move any pieces. " +
                      "Going back to the previous player.")
                self.current_turn = (self.current_turn - 1) % self.TOTAL_PLAYERS

        return {"success": True,
                "action": "move_piece",
                "board_state": self.board_state.tolist(),
                "error": "",
                "moved_piece": piece_ID,
                "new_x": valid_spot[0],
                "new_y": valid_spot[1],
                "current_turn": self.current_turn,
                "next_state": next_state}

    # ***************************** HELPER FUNCTIONS ***************************************

    def _is_valid_spot(self, x, y):
        target_x = round(x)
        target_y = round(y)

        x_error = abs(target_x - x)
        y_error = abs(target_y - y)

        # Check if spot is near a valid corner/intersection on the board
        if (x_error > self.MARGIN_OF_ERROR and
                y_error > self.MARGIN_OF_ERROR):
            # print("Too far from corner/intersection")
            return None
        elif (target_x < 0 or target_x >= self.board_size or
                target_y < 0 or target_y >= self.board_size):
            # print("Outside of the game board")
            return None
        elif (self.board_state[target_y][target_x] != -1):
            # print("Not an empty spot")
            return None
        else:
            return (target_x, target_y)

    def _piece_ID_to_coord(self, piece_ID):
        # print("The pieces ID is: " + str(pieceID))
        index = np.where(self.board_state == piece_ID)
        return index[1][0], index[0][0]

    # Takes in a piece ID and returns all the board locations that piece can move to

    def _get_possible_moves(self, piece_ID):
        # Stores all the possible moves of the piece
        # 0 means a piece can't move to that index
        # 1 means a piece can move to that index
        possible_moves = []

        x, y = self._piece_ID_to_coord(piece_ID)
        # print("Finding the possible moves for piece " + str(pieceID) + " at (" + str(x) + ", " + str(y) + ")")

        for adjacent_spot in self.adjacent_pieces[(x, y)]:
            # print("Checking the adjacent spot at (" + str(x) + ", " + str(y) + ")")

            if self._is_valid_spot(adjacent_spot[0], adjacent_spot[1]):
                possible_moves.append(adjacent_spot)

        return possible_moves

    def _get_active_pieces(self):
        active_pieces = []

        # Get the indices of the player's pieces
        # TODO: check if there is a better way to do this
        board_copy = np.copy(self.board_state)
        non_null = np.logical_and(board_copy is not None, board_copy != -1)
        board_copy[non_null] = board_copy[non_null] & (2**self.ID_SHIFT - 1)
        indices = np.where(board_copy == self.current_turn)

        # Goes through each of the player's pieces
        for i in range(len(indices[0])):
            x = indices[1][i]
            y = indices[0][i]
            id = self.board_state[y][x]
            if self._get_possible_moves(id):
                active_pieces.append(id)

        return active_pieces

    # Searches the board and returns if a new jare was made or not
    def _made_new_jare(self):
        pieces_in_jare = []
        neighboring_ally = None
        total_jare = 0

        # Get the indices of the player's pieces
        # TODO: check if there is a better way to do this
        board_copy = np.copy(self.board_state)
        non_null = np.logical_and(board_copy is not None, board_copy != -1)
        board_copy[non_null] = board_copy[non_null] & (2**self.ID_SHIFT - 1)
        indices = np.where(board_copy == self.current_turn)

        # Goes through each of the player's pieces
        for i in range(len(indices[0])):
            board_coord = (indices[1][i], indices[0][i])

            # Checks if the piece is already in another "jare"
            if board_coord in pieces_in_jare:
                # print("The game piece at " + str(board_coord) + " is already a part of a jare\n")
                continue

            # print("Investigating the game piece at " + str(board_coord))
            # Checks if any adjacent pieces are also one of the player's pieces
            for neighbor_coord in self.adjacent_pieces[board_coord]:

                if neighbor_coord in pieces_in_jare:
                    # print("The neighbor at " + str(neighbor_coord) + " is already in a jare\n")
                    continue

                elif (self.board_state[neighbor_coord[1]][neighbor_coord[0]] != -1 and
                      (self.board_state[neighbor_coord[1]][neighbor_coord[0]] & (2**self.ID_SHIFT - 1) == self.current_turn)):
                    if neighboring_ally is None:
                        neighboring_ally = neighbor_coord
                    else:
                        # print("Found a jare made of the pieces at " + str(board_coord) +
                        #  ", " + str(neighbor_coord) + ", " + str(neighboring_ally) + "\n")
                        total_jare += 1

                        # Record all the pieces that make up this jare
                        pieces_in_jare.append(board_coord)
                        pieces_in_jare.append(neighbor_coord)
                        pieces_in_jare.append(neighboring_ally)

                        # Reset the neighboring ally
                        neighboring_ally = None

                        # print()
                        break

            # Reset the neighboring ally
            neighboring_ally = None

        if self.current_jare[self.current_turn] < total_jare:
            self.current_jare[self.current_turn] = total_jare
            return True

        else:
            self.current_jare[self.current_turn] = total_jare
            return False

    # Checks if any player has satisfied the win condition
    def _is_game_over(self):
        for i in self.total_pieces:
            if i <= self.MIN_PIECES:
                return True

        return False
