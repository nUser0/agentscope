# -*- coding: utf-8 -*-
"""A dict dialog agent that using `parse_func` and `fault_handler` to
parse the model response."""
import json
from typing import Any, Optional, Union, Callable
from loguru import logger

from ..message import Msg
from .agent import AgentBase
from ..prompt import PromptEngine
from ..prompt import PromptType


class DictDialogAgent(AgentBase):
    """An agent that generates response in a dict format, where user can
    specify the required fields in the response via prompt, e.g.

    .. code-block:: python

        prompt = "... Response in the following format that can be loaded by
        python json.loads()
        {
            "thought": "thought",
            "speak": "thoughts summary to say to others",
            # ...
        }"

    This agent class is an example for using `parse_func` and `fault_handler`
    to parse the output from the model, and handling the fault when parsing
    fails. We take "speak" as a required field in the response, and print
    the speak field as the output response.

    For usage example, please refer to the example of werewolf in
    `examples/werewolf`"""

    def __init__(
        self,
        name: str,
        config: Optional[dict] = None,
        sys_prompt: Optional[str] = None,
        model: Optional[Union[Callable[..., Any], str]] = None,
        use_memory: bool = True,
        memory_config: Optional[dict] = None,
        parse_func: Optional[Callable[..., Any]] = json.loads,
        fault_handler: Optional[Callable[..., Any]] = lambda x: {"speak": x},
        max_retries: Optional[int] = 3,
        prompt_type: Optional[PromptType] = PromptType.LIST,
    ) -> None:
        """Initialize the dict dialog agent.

        Arguments:
            name (`str`):
                The name of the agent.
            config (`Optional[dict]`, defaults to `None`):
                The configuration of the agent, if provided, the agent will
                be initialized from the config rather than the other
                parameters.
            sys_prompt (`Optional[str]`, defaults to `None`):
                The system prompt of the agent, which can be passed by args
                or hard-coded in the agent.
            model (`Optional[Union[Callable[..., Any], str]]`, defaults to
            `None`):
                The callable model object or the model name, which is used to
                load model from configuration.
            use_memory (`bool`, defaults to `True`):
                Whether the agent has memory.
            memory_config (`Optional[dict]`, defaults to `None`):
                The config of memory.
            parse_func (`Optional[Callable[..., Any]]`, defaults to `None`):
                The function used to parse the model output,
                e.g. `json.loads`, which is used to extract json from the
                output.
            fault_handler (`Optional[Callable[..., Any]]`, defaults to `None`):
                The function used to handle the fault when parse_func fails
                to parse the model output.
            max_retries (`Optional[int]`, defaults to `None`):
                The maximum number of retries when failed to parse the model
                output.
            prompt_type (`Optional[PromptType]`, defaults to
            `PromptType.LIST`):
                The type of the prompt organization, chosen from
                `PromptType.LIST` or `PromptType.STRING`.
        """
        super().__init__(
            name,
            config,
            sys_prompt,
            model,
            use_memory,
            memory_config,
        )

        # record the func and handler for parsing and handling faults
        self.parse_func = parse_func
        self.fault_handler = fault_handler
        self.max_retries = max_retries

        # init prompt engine
        self.engine = PromptEngine(self.model, prompt_type=prompt_type)

    def reply(self, x: dict = None) -> dict:
        """Reply function of the agent.
        Processes the input data, generates a prompt using the current
        dialogue memory and system prompt, and invokes the language
        model to produce a response. The response is then formatted
        and added to the dialogue memory.

        Args:
            x (`dict`, defaults to `None`):
                A dictionary representing the user's input to the agent.
                This input is added to the dialogue memory if provided.
        Returns:
            A dictionary representing the message generated by the agent in
            response to the user's input. It contains at least a 'speak' key
            with the textual response and may include other keys such as
            'agreement' if provided by the language model.

        Raises:
            `json.decoder.JSONDecodeError`:
                If the response from the language model is not valid JSON,
                it defaults to treating the response as plain text.
        """
        # record the input if needed
        if x is not None:
            self.memory.add(x)

        # prepare prompt
        prompt = self.engine.join(
            self.sys_prompt,
            self.memory.get_memory(),
        )

        # call llm
        response = self.model(
            prompt,
            parse_func=self.parse_func,
            fault_handler=self.fault_handler,
            max_retries=self.max_retries,
        )

        # logging raw messages in debug mode
        logger.debug(json.dumps(response, indent=4))

        # In this agent, if the response is a dict, we treat "speak" as a
        # special key, which represents the text to be spoken
        if isinstance(response, dict) and "speak" in response:
            msg = Msg(self.name, response["speak"], **response)
        else:
            msg = Msg(self.name, response)

        # logging the message
        logger.chat(msg)

        # record to memory
        self.memory.add(msg)

        return msg