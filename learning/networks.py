import torch
from torch import nn

# Shrinks the starting output weights, so an untrained actor scores every action
# almost equally and therefore behaves like a uniform random policy.
INITIAL_OUTPUT_SCALE = 0.01


class Actor(nn.Module):

    def __init__(self, 
                 observation_size: int, 
                 action_count: int, 
                 hidden_sizes: list[int] | tuple[int, ...]) -> None:
        
        super().__init__()

        self.observation_size = observation_size
        self.action_count = action_count
        self.hidden_sizes = tuple(hidden_sizes)

        self.layers = nn.Sequential()
        
        input_size = observation_size
        for hidden_size in self.hidden_sizes:
            self.layers.append(nn.Linear(input_size, hidden_size))
            self.layers.append(nn.ReLU())
            input_size = hidden_size

        output = nn.Linear(input_size, action_count)

        with torch.no_grad():
            output.weight.mul_(INITIAL_OUTPUT_SCALE)
            output.bias.zero_()

        self.layers.append(output)


    def forward(self, observations: torch.Tensor) -> torch.Tensor:
        return self.layers(observations)


class Critic(nn.Module):

    def __init__(self,
                 observation_size: int,
                 hidden_sizes: list[int] | tuple[int, ...]) -> None:

        super().__init__()

        self.observation_size = observation_size
        self.hidden_sizes = tuple(hidden_sizes)

        self.layers = nn.Sequential()

        input_size = observation_size
        for hidden_size in self.hidden_sizes:
            self.layers.append(nn.Linear(input_size, hidden_size))
            self.layers.append(nn.ReLU())
            input_size = hidden_size

        self.layers.append(nn.Linear(input_size, 1))


    def forward(self, observations: torch.Tensor) -> torch.Tensor:
        return self.layers(observations).squeeze(-1)
