import json

import mysql.connector.errors

from gssp_experiments.database import cursor, cnx

add_message_custom = "INSERT INTO `messages_detailed` (id, user_id, channel_id, time, contents) VALUES (%s, %s, %s, %s, %s)"


class DatabaseTools():
    def __init__(self, client):
        self.client = client

    def add_message_to_db(self, message):
        from gssp_experiments.client_tools import ClientTools
        self.client_tools = ClientTools(self.client)
        is_allowed = self.client_tools.channel_allowed(message.channel.id, message.channel, message.channel.is_nsfw())
        if is_allowed:
            try:
                while True:
                    result = cursor.fetchone()
                    if result is not None:
                        print(result + " - < Unread result")
                    else:
                        break
                cursor.execute(add_message_custom, (
                    int(message.id), message.author.id, str(message.channel.id),
                    message.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    message.content,))
            except mysql.connector.errors.IntegrityError:
                pass
            except mysql.connector.errors.DataError:
                print("Couldn't insert {} - likely a time issue".format(message.id))
        cnx.commit()

    def opted_in(self, user=None, user_id=None):
        """
        ID takes priority over user if provided

        User: Logged username in DB
        ID: ID of user

        Returns true if user is opted in, false if not
        """
        if user_id is None:
            get_user = "SELECT `opted_in`, `username` FROM `users` WHERE  `username`=%s;"
        else:
            get_user = "SELECT `opted_in`, `username` FROM `users` WHERE  `user_id`=%s;"
            user = user_id
        cursor.execute(get_user, (user,))
        results = cursor.fetchall()
        try:
            if results[0][0] != 1:
                return False
        except IndexError:
            return False
        return results[0][1]

    async def save_markov(self, model, user_id):
        """
        Save a model to markov table

        user_id : user's ID we want to save for
        model: Markov model object
        """
        save = "INSERT INTO `markovs` (`user`, `markov_json`) VALUES (%s, %s);"
        save_update = "UPDATE `markovs` SET `markov_json`=%s WHERE `user`=%s;"

        try:
            cursor.execute(save, (user_id, model.to_json()))
        except mysql.connector.errors.IntegrityError:
            cursor.execute(save_update, (model.to_json(), user_id))
        cnx.commit()
        return

    async def get_blocklist(self, user_id):
        user_id = str(user_id)
        get = "SELECT blocklist FROM blocklists WHERE user_id = %s"
        cursor.execute(get, (user_id,))
        resultset = cursor.fetchall()
        if not resultset:
            # add a blank blocklist
            create_user = "INSERT INTO blocklists (user_id, blocklist) VALUES (%s, '[]')"
            cursor.execute(create_user, (user_id,))
            return []
        return json.loads(resultset[0][0])

    def is_automated(self, user):
        """
        Returns true if user is opted in to automation, false if not
        """
        cnx.commit()
        get_user = "SELECT `automate_opted_in` FROM `users` WHERE  `user_id`=%s;"
        cursor.execute(get_user, (user.id,))
        results = cursor.fetchall()
        cnx.commit()
        try:
            if results[0][0] != 1:
                return False
        except IndexError:
            return False
        return True

    async def get_messages(self, user_id, limit: int, server=False):
        """
        user_id : ID of user you want to get messages for

        Returns:

        messages: list of all messages from a user
        channels: list of all channels relevant to messages, in same order
        """
        if server:
            get_messages = "SELECT `contents`, `channel_id` FROM `messages_detailed` ORDER BY TIME DESC LIMIT " + str(
                int(limit))
            cursor.execute(get_messages)
        else:
            get_messages = "SELECT `contents`, `channel_id` FROM `messages_detailed` WHERE `user_id` = %s ORDER BY TIME DESC LIMIT " + str(
                int(limit))
            cursor.execute(get_messages, (user_id,))
        results = cursor.fetchall()
        messages = []
        channels = []
        if server is True:
            blocklist = []
        else:
            blocklist = await self.get_blocklist(user_id)
        for result in results:
            valid = True
            for word in result[0].split(" "):
                if word in blocklist:
                    valid = False
            if valid:
                messages.append(result[0])
                channels.append(result[1])

        return messages, channels