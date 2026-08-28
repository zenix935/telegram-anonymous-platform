"""Aiogram FSM States for interactive bot flows."""

from aiogram.fsm.state import State, StatesGroup


class PersonalChatStates(StatesGroup):
    """States for personal anonymous conversations."""

    waiting_for_message = State()
    replying_to_message = State()
    setting_custom_slug = State()
    setting_nickname = State()
    reporting_reason = State()


class ChannelPublishStates(StatesGroup):
    """States for channel anonymous posting."""

    waiting_for_channel_post = State()
    configuring_template = State()
    setting_channel_slug = State()
