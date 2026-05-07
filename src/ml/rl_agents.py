"""
TradingAI Bot - Reinforcement Learning Trading Agents

Inspired by Stock-Prediction-Models and TradingAgents:
- Environment for RL-based trading
- Simple policy gradient agents
- Q-learning based agents
- Optional integration (can be disabled)

This is designed to be optional - the system works without trained RL models.
Training requires significant computation and historical data.
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
from abc import ABC, abstractmethod
import logging
import pickle
from pathlib import Path

logger = logging.getLogger(__name__)


class Action(int, Enum):
    """Trading actions."""
    HOLD = 0
    BUY = 1
    SELL = 2


@dataclass
class TradingState:
    """State representation for RL environment."""
    price_features: np.ndarray  # Technical indicators
    position: float  # Current position (0 = no position, 1 = long)
    unrealized_pnl: float  # Unrealized P&L percentage
    cash_ratio: float  # Cash / Total portfolio value


class TradingEnvironment:
    """
    OpenAI Gym-style trading environment.
    
    Features:
    - Discrete action space (hold, buy, sell)
    - Continuous state space (technical features + position info)
    - Realistic execution with slippage
    """
    
    def __init__(
        self,
        df: pd.DataFrame,
        feature_columns: List[str],
        initial_capital: float = 100000.0,
        commission: float = 0.001,
        slippage: float = 0.001,
        max_position: float = 1.0
    ):
        """
        Initialize environment.
        
        Args:
            df: DataFrame with price data and features
            feature_columns: List of columns to use as state features
            initial_capital: Starting capital
            commission: Commission rate per trade
            slippage: Slippage rate per trade
            max_position: Maximum position size (1.0 = 100% of capital)
        """
        self.df = df.copy()
        self.feature_columns = feature_columns
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        self.max_position = max_position
        
        # Extract features
        self.features = df[feature_columns].values
        self.prices = df['close'].values
        
        # State
        self.current_step = 0
        self.cash = initial_capital
        self.position = 0.0
        self.entry_price = 0.0
        self.total_pnl = 0.0
        
        # Episode tracking
        self.history = []
    
    @property
    def state_dim(self) -> int:
        """Dimension of state space."""
        return len(self.feature_columns) + 3  # features + position + pnl + cash_ratio
    
    @property
    def action_dim(self) -> int:
        """Dimension of action space."""
        return 3  # hold, buy, sell
    
    def reset(self) -> TradingState:
        """Reset environment to initial state."""
        self.current_step = 0
        self.cash = self.initial_capital
        self.position = 0.0
        self.entry_price = 0.0
        self.total_pnl = 0.0
        self.history = []
        
        return self._get_state()
    
    def step(self, action: Action) -> Tuple[TradingState, float, bool, Dict]:
        """
        Execute action and return (state, reward, done, info).
        
        Args:
            action: Trading action to take
        
        Returns:
            Tuple of (next_state, reward, done, info_dict)
        """
        current_price = self.prices[self.current_step]
        prev_portfolio_value = self._get_portfolio_value(current_price)
        
        # Execute action
        executed = False
        
        if action == Action.BUY and self.position == 0:
            # Buy
            exec_price = current_price * (1 + self.slippage)
            position_value = self.cash * self.max_position
            shares = position_value / exec_price
            cost = position_value * (1 + self.commission)
            
            if cost <= self.cash:
                self.cash -= cost
                self.position = shares
                self.entry_price = exec_price
                executed = True
        
        elif action == Action.SELL and self.position > 0:
            # Sell
            exec_price = current_price * (1 - self.slippage)
            proceeds = self.position * exec_price * (1 - self.commission)
            pnl = proceeds - (self.position * self.entry_price)
            
            self.cash += proceeds
            self.total_pnl += pnl
            self.position = 0
            self.entry_price = 0
            executed = True
        
        # Move to next step
        self.current_step += 1
        done = self.current_step >= len(self.prices) - 1
        
        # Calculate reward
        next_price = self.prices[self.current_step] if not done else current_price
        new_portfolio_value = self._get_portfolio_value(next_price)
        
        # Reward = change in portfolio value (percentage)
        reward = (new_portfolio_value - prev_portfolio_value) / prev_portfolio_value
        
        # Penalize holding (opportunity cost)
        if action == Action.HOLD:
            reward -= 0.0001  # Small penalty for inaction
        
        # Record history
        self.history.append({
            'step': self.current_step,
            'price': current_price,
            'action': action.name,
            'position': self.position,
            'portfolio_value': new_portfolio_value,
            'reward': reward
        })
        
        info = {
            'executed': executed,
            'portfolio_value': new_portfolio_value,
            'position': self.position,
            'cash': self.cash,
            'total_pnl': self.total_pnl
        }
        
        return self._get_state(), reward, done, info
    
    def _get_state(self) -> TradingState:
        """Get current state representation."""
        current_price = self.prices[self.current_step]
        portfolio_value = self._get_portfolio_value(current_price)
        
        # Unrealized P&L
        if self.position > 0 and self.entry_price > 0:
            unrealized_pnl = (current_price / self.entry_price) - 1
        else:
            unrealized_pnl = 0.0
        
        # Cash ratio
        cash_ratio = self.cash / portfolio_value if portfolio_value > 0 else 1.0
        
        return TradingState(
            price_features=self.features[self.current_step],
            position=1.0 if self.position > 0 else 0.0,
            unrealized_pnl=unrealized_pnl,
            cash_ratio=cash_ratio
        )
    
    def _get_portfolio_value(self, current_price: float) -> float:
        """Calculate total portfolio value."""
        position_value = self.position * current_price
        return self.cash + position_value
    
    def get_state_array(self, state: TradingState) -> np.ndarray:
        """Convert TradingState to numpy array for RL model."""
        return np.concatenate([
            state.price_features,
            [state.position, state.unrealized_pnl, state.cash_ratio]
        ])


class RLAgent(ABC):
    """Abstract base class for RL trading agents."""
    
    @abstractmethod
    def select_action(self, state: np.ndarray, training: bool = False) -> Action:
        """Select action given state."""
        pass
    
    @abstractmethod
    def update(self, state: np.ndarray, action: Action, reward: float, next_state: np.ndarray, done: bool):
        """Update agent from experience."""
        pass
    
    @abstractmethod
    def save(self, path: str):
        """Save model to file."""
        pass
    
    @abstractmethod
    def load(self, path: str):
        """Load model from file."""
        pass


class SimpleQLearningAgent(RLAgent):
    """
    Simple Q-learning agent with discretized state space.
    
    Good for learning basic trading rules with limited state complexity.
    """
    
    def __init__(
        self,
        state_dim: int,
        action_dim: int = 3,
        learning_rate: float = 0.1,
        discount_factor: float = 0.95,
        epsilon: float = 1.0,
        epsilon_decay: float = 0.995,
        epsilon_min: float = 0.01,
        n_bins: int = 10
    ):
        """
        Initialize Q-learning agent.
        
        Args:
            state_dim: Dimension of state space
            action_dim: Number of possible actions
            learning_rate: Learning rate (alpha)
            discount_factor: Discount factor (gamma)
            epsilon: Initial exploration rate
            epsilon_decay: Epsilon decay per episode
            epsilon_min: Minimum epsilon
            n_bins: Number of bins for state discretization
        """
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.lr = learning_rate
        self.gamma = discount_factor
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.epsilon_min = epsilon_min
        self.n_bins = n_bins
        
        # Q-table (discretized states -> action values)
        self.q_table: Dict[Tuple, np.ndarray] = {}
        
        # State discretization bins (learned from data)
        self.state_bins: List[np.ndarray] = []
    
    def initialize_bins(self, states: np.ndarray):
        """Initialize discretization bins from sample states."""
        self.state_bins = []
        for i in range(states.shape[1]):
            bins = np.percentile(states[:, i], np.linspace(0, 100, self.n_bins + 1)[1:-1])
            self.state_bins.append(bins)
    
    def discretize_state(self, state: np.ndarray) -> Tuple:
        """Convert continuous state to discrete tuple."""
        discrete = []
        for i, value in enumerate(state):
            if i < len(self.state_bins):
                bin_idx = np.digitize(value, self.state_bins[i])
            else:
                bin_idx = int(value * self.n_bins)  # Simple discretization
            discrete.append(bin_idx)
        return tuple(discrete)
    
    def get_q_values(self, state: Tuple) -> np.ndarray:
        """Get Q-values for discretized state."""
        if state not in self.q_table:
            self.q_table[state] = np.zeros(self.action_dim)
        return self.q_table[state]
    
    def select_action(self, state: np.ndarray, training: bool = False) -> Action:
        """Select action using epsilon-greedy policy."""
        discrete_state = self.discretize_state(state)
        
        if training and np.random.random() < self.epsilon:
            return Action(np.random.randint(self.action_dim))
        
        q_values = self.get_q_values(discrete_state)
        return Action(np.argmax(q_values))
    
    def update(
        self,
        state: np.ndarray,
        action: Action,
        reward: float,
        next_state: np.ndarray,
        done: bool
    ):
        """Update Q-table using Q-learning update rule."""
        s = self.discretize_state(state)
        s_next = self.discretize_state(next_state)
        
        # Q-learning update
        current_q = self.get_q_values(s)[action.value]
        
        if done:
            target = reward
        else:
            max_next_q = np.max(self.get_q_values(s_next))
            target = reward + self.gamma * max_next_q
        
        # Update Q-value
        self.q_table[s][action.value] = current_q + self.lr * (target - current_q)
    
    def decay_epsilon(self):
        """Decay exploration rate."""
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)
    
    def save(self, path: str):
        """Save agent to file."""
        data = {
            'q_table': self.q_table,
            'state_bins': self.state_bins,
            'epsilon': self.epsilon,
            'config': {
                'state_dim': self.state_dim,
                'action_dim': self.action_dim,
                'lr': self.lr,
                'gamma': self.gamma
            }
        }
        with open(path, 'wb') as f:
            pickle.dump(data, f)
    
    def load(self, path: str):
        """Load agent from file."""
        with open(path, 'rb') as f:
            data = pickle.load(f)
        self.q_table = data['q_table']
        self.state_bins = data['state_bins']
        self.epsilon = data['epsilon']


class PolicyGradientAgent(RLAgent):
    """
    Simple policy gradient (REINFORCE) agent.
    
    Uses neural network to learn policy directly.
    Requires PyTorch or similar (optional dependency).
    """
    
    def __init__(
        self,
        state_dim: int,
        action_dim: int = 3,
        hidden_dim: int = 64,
        learning_rate: float = 0.001,
        discount_factor: float = 0.99
    ):
        """
        Initialize policy gradient agent.
        
        Args:
            state_dim: Dimension of state space
            action_dim: Number of possible actions
            hidden_dim: Size of hidden layer
            learning_rate: Learning rate
            discount_factor: Discount factor (gamma)
        """
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.hidden_dim = hidden_dim
        self.lr = learning_rate
        self.gamma = discount_factor
        
        # Check if PyTorch is available
        self.use_torch = False
        try:
            import torch
            import torch.nn as nn
            self.use_torch = True
            self._init_torch_model(torch, nn)
        except ImportError:
            logger.warning("PyTorch not installed. Using simple linear policy.")
            self._init_simple_model()
        
        # Episode memory
        self.saved_log_probs = []
        self.rewards = []
    
    def _init_torch_model(self, torch, nn):
        """Initialize PyTorch policy network."""
        self.torch = torch
        
        class PolicyNetwork(nn.Module):
            def __init__(self, state_dim, action_dim, hidden_dim):
                super().__init__()
                self.fc1 = nn.Linear(state_dim, hidden_dim)
                self.fc2 = nn.Linear(hidden_dim, hidden_dim)
                self.fc3 = nn.Linear(hidden_dim, action_dim)
                self.softmax = nn.Softmax(dim=-1)
            
            def forward(self, x):
                x = torch.relu(self.fc1(x))
                x = torch.relu(self.fc2(x))
                x = self.softmax(self.fc3(x))
                return x
        
        self.policy = PolicyNetwork(self.state_dim, self.action_dim, self.hidden_dim)
        self.optimizer = torch.optim.Adam(self.policy.parameters(), lr=self.lr)
    
    def _init_simple_model(self):
        """Initialize simple linear model without PyTorch."""
        self.weights = np.random.randn(self.state_dim, self.action_dim) * 0.01
    
    def select_action(self, state: np.ndarray, training: bool = False) -> Action:
        """Select action using policy network."""
        if self.use_torch:
            return self._select_action_torch(state, training)
        else:
            return self._select_action_simple(state, training)
    
    def _select_action_torch(self, state: np.ndarray, training: bool) -> Action:
        """Select action using PyTorch policy."""
        state_tensor = self.torch.FloatTensor(state).unsqueeze(0)
        probs = self.policy(state_tensor)
        
        if training:
            dist = self.torch.distributions.Categorical(probs)
            action = dist.sample()
            self.saved_log_probs.append(dist.log_prob(action))
            return Action(action.item())
        else:
            return Action(probs.argmax().item())
    
    def _select_action_simple(self, state: np.ndarray, training: bool) -> Action:
        """Select action using simple linear policy."""
        logits = np.dot(state, self.weights)
        probs = np.exp(logits) / np.sum(np.exp(logits))
        
        if training:
            action = np.random.choice(self.action_dim, p=probs)
        else:
            action = np.argmax(probs)
        
        return Action(action)
    
    def update(
        self,
        state: np.ndarray,
        action: Action,
        reward: float,
        next_state: np.ndarray,
        done: bool
    ):
        """Store reward for episode update."""
        self.rewards.append(reward)
        
        if done:
            self._update_policy()
    
    def _update_policy(self):
        """Update policy at end of episode."""
        if not self.use_torch:
            return  # Skip for simple model
        
        # Calculate discounted returns
        R = 0
        returns = []
        for r in reversed(self.rewards):
            R = r + self.gamma * R
            returns.insert(0, R)
        
        returns = self.torch.FloatTensor(returns)
        
        # Normalize returns
        if len(returns) > 1:
            returns = (returns - returns.mean()) / (returns.std() + 1e-8)
        
        # Calculate policy loss
        policy_loss = []
        for log_prob, R in zip(self.saved_log_probs, returns):
            policy_loss.append(-log_prob * R)
        
        # Update
        self.optimizer.zero_grad()
        loss = self.torch.cat(policy_loss).sum()
        loss.backward()
        self.optimizer.step()
        
        # Clear episode memory
        self.saved_log_probs = []
        self.rewards = []
    
    def save(self, path: str):
        """Save agent to file."""
        if self.use_torch:
            self.torch.save({
                'policy_state_dict': self.policy.state_dict(),
                'optimizer_state_dict': self.optimizer.state_dict(),
                'config': {
                    'state_dim': self.state_dim,
                    'action_dim': self.action_dim,
                    'hidden_dim': self.hidden_dim
                }
            }, path)
        else:
            np.save(path, self.weights)
    
    def load(self, path: str):
        """Load agent from file."""
        if self.use_torch:
            checkpoint = self.torch.load(path)
            self.policy.load_state_dict(checkpoint['policy_state_dict'])
            self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        else:
            self.weights = np.load(path)


class RLTrainer:
    """
    Trainer for RL trading agents.
    
    Handles:
    - Training loop
    - Evaluation
    - Logging and checkpointing
    """
    
    def __init__(
        self,
        env: TradingEnvironment,
        agent: RLAgent,
        checkpoint_dir: Optional[str] = None
    ):
        """
        Initialize trainer.
        
        Args:
            env: Trading environment
            agent: RL agent
            checkpoint_dir: Directory for saving checkpoints
        """
        self.env = env
        self.agent = agent
        self.checkpoint_dir = Path(checkpoint_dir) if checkpoint_dir else None
        
        if self.checkpoint_dir:
            self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        # Training history
        self.episode_rewards = []
        self.episode_portfolio_values = []
    
    def train(
        self,
        n_episodes: int = 100,
        log_interval: int = 10,
        save_interval: int = 50
    ) -> Dict[str, List[float]]:
        """
        Train agent for specified number of episodes.
        
        Args:
            n_episodes: Number of training episodes
            log_interval: Interval for logging progress
            save_interval: Interval for saving checkpoints
        
        Returns:
            Training history
        """
        for episode in range(n_episodes):
            state = self.env.reset()
            state_array = self.env.get_state_array(state)
            
            total_reward = 0
            done = False
            
            while not done:
                action = self.agent.select_action(state_array, training=True)
                next_state, reward, done, info = self.env.step(action)
                next_state_array = self.env.get_state_array(next_state)
                
                self.agent.update(state_array, action, reward, next_state_array, done)
                
                state_array = next_state_array
                total_reward += reward
            
            # Decay epsilon for Q-learning
            if hasattr(self.agent, 'decay_epsilon'):
                self.agent.decay_epsilon()
            
            # Record metrics
            final_value = info['portfolio_value']
            self.episode_rewards.append(total_reward)
            self.episode_portfolio_values.append(final_value)
            
            # Logging
            if (episode + 1) % log_interval == 0:
                avg_reward = np.mean(self.episode_rewards[-log_interval:])
                avg_value = np.mean(self.episode_portfolio_values[-log_interval:])
                logger.info(
                    f"Episode {episode + 1}/{n_episodes} | "
                    f"Avg Reward: {avg_reward:.4f} | "
                    f"Avg Portfolio: ${avg_value:,.0f}"
                )
            
            # Save checkpoint
            if self.checkpoint_dir and (episode + 1) % save_interval == 0:
                self.agent.save(str(self.checkpoint_dir / f"agent_ep{episode + 1}.pkl"))
        
        return {
            'rewards': self.episode_rewards,
            'portfolio_values': self.episode_portfolio_values
        }
    
    def evaluate(self, n_episodes: int = 10) -> Dict[str, float]:
        """
        Evaluate trained agent.
        
        Args:
            n_episodes: Number of evaluation episodes
        
        Returns:
            Evaluation metrics
        """
        rewards = []
        portfolio_values = []
        win_rates = []
        
        for _ in range(n_episodes):
            state = self.env.reset()
            state_array = self.env.get_state_array(state)
            
            total_reward = 0
            wins = 0
            total_trades = 0
            done = False
            
            while not done:
                action = self.agent.select_action(state_array, training=False)
                next_state, reward, done, info = self.env.step(action)
                next_state_array = self.env.get_state_array(next_state)
                
                state_array = next_state_array
                total_reward += reward
                
                if action != Action.HOLD and info['executed']:
                    total_trades += 1
                    if reward > 0:
                        wins += 1
            
            rewards.append(total_reward)
            portfolio_values.append(info['portfolio_value'])
            win_rates.append(wins / total_trades if total_trades > 0 else 0)
        
        return {
            'avg_reward': np.mean(rewards),
            'avg_portfolio_value': np.mean(portfolio_values),
            'avg_return': np.mean(portfolio_values) / self.env.initial_capital - 1,
            'avg_win_rate': np.mean(win_rates),
            'std_reward': np.std(rewards),
            'std_portfolio': np.std(portfolio_values)
        }


class RLSignalGenerator:
    """
    Generate trading signals from trained RL agent.
    
    Integrates with the existing signal pipeline.
    """
    
    def __init__(
        self,
        agent: RLAgent,
        feature_columns: List[str],
        confidence_threshold: float = 0.6
    ):
        """
        Initialize signal generator.
        
        Args:
            agent: Trained RL agent
            feature_columns: Columns to use as features
            confidence_threshold: Minimum confidence for signals
        """
        self.agent = agent
        self.feature_columns = feature_columns
        self.confidence_threshold = confidence_threshold
    
    def generate_signal(
        self,
        df: pd.DataFrame,
        current_position: float = 0.0
    ) -> Dict[str, Any]:
        """
        Generate trading signal for current state.
        
        Args:
            df: DataFrame with price data and features
            current_position: Current position (0 = none, 1 = long)
        
        Returns:
            Signal dict with action and confidence
        """
        if len(df) < 1:
            return {'action': 'hold', 'confidence': 0.0}
        
        # Extract features
        features = df[self.feature_columns].iloc[-1].values
        
        # Add position info
        unrealized_pnl = 0.0  # Would need actual position tracking
        cash_ratio = 1.0 if current_position == 0 else 0.0
        
        state = np.concatenate([
            features,
            [current_position, unrealized_pnl, cash_ratio]
        ])
        
        # Get action from agent
        action = self.agent.select_action(state, training=False)
        
        # Map to signal
        action_map = {
            Action.HOLD: 'hold',
            Action.BUY: 'buy',
            Action.SELL: 'sell'
        }
        
        # For now, use fixed confidence
        # In production, this could use action probabilities
        confidence = 0.7 if action != Action.HOLD else 0.5
        
        return {
            'action': action_map[action],
            'confidence': confidence,
            'timestamp': df.index[-1] if hasattr(df.index, '__getitem__') else None
        }
