import concurrent

import discord

from gssp_experiments.database.database_tools import DatabaseTools
from gssp_experiments.settings.config import config, strings

disabled_groups = config['discord']['disabled_groups']


class ClientTools():

    def __init__(self, client):
        self.database_tools = DatabaseTools(client)
        self.client = client

    def channel_allowed(self, channel_id, existing_channel, nsfw=False):
        """
        Check if a channel is allowed in current context

        channel_id: ID of channel
        existing_channel: channel object of existing channel
        nsfw: whether to only return NSFW channels
        """
        channel = self.client.get_channel(int(channel_id))

        for group in disabled_groups:
            if str(channel.category).lower() == str(group).lower():
                return False

        if not existing_channel.is_nsfw() and bool(nsfw):
            return False

        if channel.is_nsfw():
            return bool(nsfw)  # checks if user wants / is allowed explicit markovs
            # this means that if the channel *is* NSFW, we return True, but if it isn't, we return False
        else:  # channel is SFW
            if bool(nsfw):
                return False  # this stops SFW chats from being included in NSFW markovs

        return True

    async def build_messages(self, ctx, nsfw, messages, channels, selected_channel=None):
        """
            Returns/appends to a list messages from a user
            Params:
            messages: list of messages
            channel: list of channels for messages
            selected_channel: Not required, but channel to filter to. If none, filtering is disabled.
            text = list of text that already exists. If not set, we just create one
        """
        text = []

        for counter, m in enumerate(messages):

            if self.channel_allowed(channels[counter], ctx.message.channel, nsfw):
                if selected_channel is not None:
                    if self.client.get_channel(int(channels[counter])).id == selected_channel.id:
                        text.append(m)
                else:
                    text.append(m)
        return text

    async def get_delete_emoji(self):
        delete_emoji = self.client.get_emoji(int(strings['emojis']['delete']))
        if delete_emoji is not None:
            emoji_name = delete_emoji.name
        else:
            emoji_name = "❌"
        return emoji_name, delete_emoji

    async def markov_embed(self, title, message):
        em = discord.Embed(title=title, description=message)
        name = await self.get_delete_emoji()
        name = name[0]
        em.set_footer(text=strings['markov']['output']['footer'].format(name))
        return em

    async def delete_option(self, client, message, ctx, delete_emoji, timeout=config['discord']['delete_timeout']):
        """Utility function that allows for you to add a delete option to the end of a command.
        This makes it easier for users to control the output of commands, esp handy for random output ones."""
        await message.add_reaction(delete_emoji)

        def check(r, u):
            return str(r) == str(delete_emoji) and u == ctx.author and r.message.id == message.id

        try:
            await client.wait_for("reaction_add", timeout=timeout, check=check)
            await message.remove_reaction(delete_emoji, client.user)
            await message.remove_reaction(delete_emoji, ctx.author)
            em = discord.Embed(title=str(ctx.message.author) +
                                     " deleted message", description="User deleted this message.")

            return await message.edit(embed=em)
        except concurrent.futures._base.TimeoutError:
            await message.remove_reaction(delete_emoji, client.user)

    async def build_data_profile(self, members, limit=50000):
        """
        Used for building a data profile based on a user

        Members: list of members we want to import for
        Guild: Guild object
        Limit: limit of messages to be imported
        """
        for guild in self.client.guilds:
            for cur_channel in guild.text_channels:
                adding = True
                for group in disabled_groups:
                    try:
                        if cur_channel.category.name.lower() == group.lower():
                            adding = False
                            break
                    except AttributeError:
                        adding = False
                if adding:
                    counter = 0
                    already_added = 0
                    async for message in cur_channel.history(limit=limit, reverse=True):
                        if message.author in members:
                            self.database_tools.add_message_to_db(message)
                    print(
                        "{} scraped for {} users - added {} messages, found {} already added".format(cur_channel.name,
                                                                                                     len(members),
                                                                                                     counter,
                                                                                                     already_added))
