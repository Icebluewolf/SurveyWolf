from abc import ABC, abstractmethod
from typing import Self

import discord.ui

from questions.survey_question import SurveyQuestion


class InputTextResponse(SurveyQuestion, ABC):
    @abstractmethod
    def get_input_text(self) -> discord.ui.InputText:
        """
        Creates an InputText that fits the questions requirements
        :return: The InputText
        """
        raise NotImplementedError

    @abstractmethod
    async def handle_input_text_response(self, text: str) -> str | None:
        """
        Checks if the given input meets the questions criteria.
        If the input meets the criteria it is set as the value of the question.
        Otherwise, an error is returned
        :param text: The text from the InputText in the submitted modal
        :return: An error in the form of a string or None if there are no errors
        """
        raise NotImplementedError

    async def send_question(self, interaction: discord.Interaction, group: list[Self] = None) -> discord.Interaction:
        modal = GetResponse(group or [self])
        await interaction.response.send_modal(modal)
        await modal.wait()
        return modal.interaction


class GetResponse(discord.ui.Modal):
    def __init__(self, questions: list[InputTextResponse]):
        super().__init__(title="Type Your Answer Below")
        for question in questions:
            self.add_item(question.get_input_text())
        self.questions = questions
        self.interaction = None

    async def callback(self, interaction: discord.Interaction):
        self.interaction = interaction
        errors = []
        for n, question in enumerate(self.questions):
            e = await question.handle_input_text_response(self.children[n].value)
            if e is not None:
                errors.append(e)

        self.stop()
