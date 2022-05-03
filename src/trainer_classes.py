import numpy as np
from rlgym.utils.common_values import ORANGE_TEAM, BLUE_TEAM, ORANGE_GOAL_BACK, BLUE_GOAL_BACK, ORANGE_GOAL_CENTER, BLUE_GOAL_CENTER, BACK_WALL_Y, CAR_MAX_SPEED, BALL_MAX_SPEED
from rlgym.utils.reward_functions.common_rewards.conditional_rewards import ConditionalRewardFunction
from rlgym.utils import RewardFunction, math
from rlgym.utils.gamestates import PlayerData, GameState
from typing import List

class TeamSpacingReward(RewardFunction):
    def __init__(self, min_spacing: float = 1000) -> None:
        super().__init__()
        self.min_spacing = min_spacing

    def reset(self, initial_state: GameState):
        pass

    def get_reward(
        self, player: PlayerData, state: GameState, previous_action: np.ndarray
    ) -> float:
        reward = 0
        for p in state.players:
            if p.team_num == player.team_num and p.car_id != player.car_id and not player.is_demoed and not p.is_demoed:
                separation = np.linalg.norm(player.car_data.position - p.car_data.position)
                if separation < self.min_spacing:
                    reward -= 1-(separation / self.min_spacing)
        return reward

class FlipReward(RewardFunction): #multiply by speed?
    def __init__(self) -> None:
        super().__init__()
        self.rewarded = False

    def reset(self, initial_state: GameState):
        self.rewarded = False

    def get_reward(
        self, player: PlayerData, state: GameState, previous_action: np.ndarray
    ) -> float:
        if not player.has_flip and not self.rewarded:
            self.rewarded = True
            return 1
        elif player.has_flip:
            self.rewarded = False
        elif not player.on_ground:
            return 0.1
        return 0

class pickupBoost(RewardFunction):
    def __init__(self) -> None:
        super().__init__()
        self.lastBoost = 100

    def reset(self, initial_state: GameState):
        self.lastBoost = 100

    def get_reward(
        self, player: PlayerData, state: GameState, previous_action: np.ndarray
    ) -> float:
        if player.boost_amount > self.lastBoost + 12:
            self.lastBoost = player.boost_amount
            return 1
        elif player.boost_amount > self.lastBoost:
            self.lastBoost = player.boost_amount
            return 0.2
        self.lastBoost = player.boost_amount
        return 0

class LiuDistancePlayerToGoalReward(RewardFunction):
    def __init__(self, own_goal=True):
        super().__init__()
        self.own_goal = own_goal

    def reset(self, initial_state: GameState):
        pass

    def get_reward(self, player: PlayerData, state: GameState, previous_action: np.ndarray) -> float:
        if player.team_num == BLUE_TEAM and not self.own_goal \
                or player.team_num == ORANGE_TEAM and self.own_goal:
            objective = np.array(ORANGE_GOAL_CENTER)
        else:
            objective = np.array(BLUE_GOAL_CENTER)

        # Compensate for moving objective to back of net
        dist = np.linalg.norm(player.car_data.position - objective)
        return np.exp(-0.5 * dist / CAR_MAX_SPEED)

def playerCrossedHalfWay(player: PlayerData):
    playerY = player.car_data.position[1]
    if player.team_num == ORANGE_TEAM:
        playerY = -playerY
    return playerY > 0

def ballCrossedHalfWay(player: PlayerData, state: GameState):
    ballY = state.ball.position[1]
    if player.team_num == ORANGE_TEAM:
        ballY = -ballY
    return ballY > 0

def playerAtGoal(player: PlayerData, own_goal: bool=False):
    playerY = player.car_data.position[1]
    if player.team_num == ORANGE_TEAM:
        playerY = -playerY
    if own_goal:
        playerY = -playerY
    return playerY > BACK_WALL_Y/2

def ballAtGoal(player: PlayerData, state: GameState, own_goal: bool=False):
    ballY = state.ball.position[1]
    if player.team_num == ORANGE_TEAM:
        ballY = -ballY
    if own_goal:
        ballY = -ballY
    return ballY > BACK_WALL_Y/2

def playerApproachingGoal(player: PlayerData, own_goal: bool=False):
    if player.team_num == BLUE_TEAM and not own_goal \
            or player.team_num == ORANGE_TEAM and own_goal:
        objective = np.array(ORANGE_GOAL_BACK)
    else:
        objective = np.array(BLUE_GOAL_BACK)

    vel = player.car_data.linear_velocity
    pos_diff = objective - player.car_data.position
    # Vector version of v=d/t <=> t=d/v <=> 1/t=v/d
    # Max value should be max_speed / ball_radius = 2300 / 94 = 24.5
    # Used to guide the agent towards the ball
    return math.scalar_projection(vel, pos_diff) > 0
    """else:
        # Regular component velocity
        norm_pos_diff = pos_diff / np.linalg.norm(pos_diff)
        vel /= CAR_MAX_SPEED
        return float(np.dot(norm_pos_diff, vel))"""

def ballApproachingGoal(state: GameState, team: int):
    if team == ORANGE_TEAM:
        objective = np.array(ORANGE_GOAL_BACK)
    else:
        objective = np.array(BLUE_GOAL_BACK)

    vel = state.ball.linear_velocity
    pos_diff = objective - state.ball.position
    # Vector version of v=d/t <=> t=d/v <=> 1/t=v/d
    # Max value should be max_speed / ball_radius = 2300 / 94 = 24.5
    # Used to guide the agent towards the ball
    return math.scalar_projection(vel, pos_diff) > 0
    """else:
        # Regular component velocity
        norm_pos_diff = pos_diff / np.linalg.norm(pos_diff)
        vel /= BALL_MAX_SPEED
        return float(np.dot(norm_pos_diff, vel))"""

def attacking(player: PlayerData, state: GameState):
    if player.is_demoed:
        return False
    return playerCrossedHalfWay(player) and (playerApproachingGoal(player) or ballApproachingGoal(state, player.team_num)
            or ballAtGoal(player, state))


class RewardIfAttacking(ConditionalRewardFunction):
    def condition(self, player: PlayerData, state: GameState, previous_action: np.ndarray) -> bool:
        return attacking(player, state)

def defending(player: PlayerData, state: GameState):
    if player.is_demoed:
        return False
    return not playerCrossedHalfWay(player) and (not (playerApproachingGoal(player) and ballApproachingGoal(state, player.team_num))
            or ballAtGoal(player, state, True))

class RewardIfDefending(ConditionalRewardFunction):
    def condition(self, player: PlayerData, state: GameState, previous_action: np.ndarray) -> bool:
        return defending(player, state)

class RewardIfLastMan(ConditionalRewardFunction):
    def condition(self, player: PlayerData, state: GameState, previous_action: np.ndarray) -> bool:
        if not ballAtGoal(player, state) and (playerCrossedHalfWay(player) or (ballCrossedHalfWay(player, state) and not ballApproachingGoal(state, player.team_num))):
            return False
        teammates = 0
        teammatesAttacking = 0
        for p in state.players:
            if p.team_num == player.team_num and p.car_id != player.car_id and not p.is_demoed:
                teammates += 1
                if attacking(p, state):
                    teammatesAttacking += 1
        return teammatesAttacking == teammates - 1

class RewardIfKickoff(ConditionalRewardFunction):
    def condition(self, player: PlayerData, state: GameState, previous_action: np.ndarray) -> bool:
        return state.ball.position[0] == 0 and state.ball.position[1] == 0 and np.linalg.norm(player.car_data.linear_velocity) == 0

class RewardIfFurthestFromBall(ConditionalRewardFunction):
    def __init__(self, reward_func: RewardFunction, team_only=True):
        super().__init__(reward_func)
        self.team_only = team_only

    def condition(self, player: PlayerData, state: GameState, previous_action: np.ndarray) -> bool:
        dist = np.linalg.norm(player.car_data.position - state.ball.position)
        for player2 in state.players:
            if not self.team_only or player2.team_num == player.team_num:
                dist2 = np.linalg.norm(player2.car_data.position - state.ball.position)
                if dist2 > dist:
                    return False
        return True

class RewardIfMidFromBall(ConditionalRewardFunction):
    def __init__(self, reward_func: RewardFunction, team_only=True):
        super().__init__(reward_func)
        self.team_only = team_only

    def condition(self, player: PlayerData, state: GameState, previous_action: np.ndarray) -> bool:
        dist = np.linalg.norm(player.car_data.position - state.ball.position)
        min = max = dist
        for player2 in state.players:
            if not self.team_only or player2.team_num == player.team_num:
                dist2 = np.linalg.norm(player2.car_data.position - state.ball.position)
                if dist2 > max:
                    max = dist2
                if dist2 < min:
                    min = dist2
        return dist != max and dist != min


#crowd-sourced

class JumpTouchReward(RewardFunction):
    """
    a ball touch reward that only triggers when the agent's wheels aren't in contact with the floor
    adjust minimum ball height required for reward with 'min_height' as well as reward scaling with 'exp'
    """
    
    def __init__(self, min_height=92, exp=0.2):
        self.min_height = min_height
        self.exp = exp

    def reset(self, initial_state: GameState):
        pass

    def get_reward(
        self, player: PlayerData, state: GameState, previous_action: np.ndarray
    ) -> float:
        if player.ball_touched and not player.on_ground and state.ball.position[2] >= self.min_height:
            return ((state.ball.position[2] - 92) ** self.exp)-1

        return 0