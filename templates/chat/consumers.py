import json
from channels.generic.websocket import WebsocketConsumer
from asgiref.sync import async_to_sync
from .models import Message, Reaction

class ChatConsumer(WebsocketConsumer):
    def connect(self):
        async_to_sync(self.channel_layer.group_add)("chat", self.channel_name)
        self.accept()

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)("chat", self.channel_name)

    def receive(self, text_data):
        data = json.loads(text_data)
        action = data.get('action')
        user = self.scope["user"]
        if action == 'send_message':
            content = data.get('content', '').strip()
            parent_id = data.get('parent_id')
            if not user.is_authenticated or not content:
                return
            parent_msg = None
            if parent_id:
                parent_msg = Message.objects.filter(id=parent_id).first()
            message = Message.objects.create(user=user, content=content, parent=parent_msg)
            response = {
                'action': 'new_message',
                'id': message.id,
                'content': message.content,
                'parent_id': parent_id,
                'user': user.username,
                'created_at': message.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                'like_count': message.get_like_count(),
                'dislike_count': message.get_dislike_count(),
            }
            async_to_sync(self.channel_layer.group_send)("chat", {"type": "chat_message", "message": response})
        elif action == 'react':
            msg_id = data.get('message_id')
            reaction_type = data.get('reaction')
            if reaction_type not in [Reaction.LIKE, Reaction.DISLIKE]:
                return
            message = Message.objects.filter(id=msg_id).first()
            if not message:
                return
            react_obj = Reaction.objects.filter(message=message, user=user).first()
            if react_obj:
                if react_obj.type == reaction_type:
                    react_obj.delete()
                else:
                    react_obj.type = reaction_type
                    react_obj.save()
            else:
                Reaction.objects.create(message=message, user=user, type=reaction_type)
            like_count = message.get_like_count()
            dislike_count = message.get_dislike_count()
            response = {
                'action': 'reaction_update',
                'id': message.id,
                'like_count': like_count,
                'dislike_count': dislike_count,
            }
            async_to_sync(self.channel_layer.group_send)("chat", {"type": "chat_message", "message": response})
        elif action == 'delete':
            msg_id = data.get('message_id')
            message = Message.objects.filter(id=msg_id).first()
            if message and (message.user == user or user.is_superuser):
                message.delete()
                response = {'action': 'delete', 'id': msg_id}
                async_to_sync(self.channel_layer.group_send)("chat", {"type": "chat_message", "message": response})

    def chat_message(self, event):
        self.send(text_data=json.dumps(event['message']))
