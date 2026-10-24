import logging
import mimetypes

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Conversation, CustomUser, Message, MessageRecipient, UserStatus
from .serializers import (
    ConversationSerializer,
    FileUploadSerializer,
    MessageCreateSerializer,
    MessageSerializer,
    MessagingUserSerializer,
    UserStatusSerializer,
)

logger = logging.getLogger(__name__)


def _direct_conversation_between(user_a, user_b):
    """Return the newest exact one-to-one conversation between two users."""
    return (
        Conversation.objects
        .filter(is_active=True, participants=user_a)
        .filter(participants=user_b)
        .annotate(participant_count=Count('participants', distinct=True))
        .filter(participant_count=2)
        .order_by('-updated_at', '-created_at')
        .first()
    )


def _touch_conversation(conversation):
    Conversation.objects.filter(pk=conversation.pk).update(updated_at=timezone.now())


def _create_delivery_rows_and_notify(message):
    """Create per-user unread state and send the same OppoGlobe push/in-app alert used elsewhere."""
    recipients = list(message.conversation.participants.exclude(pk=message.sender_id))
    if not recipients:
        return

    MessageRecipient.objects.bulk_create(
        [
            MessageRecipient(message=message, recipient=user, is_read=False)
            for user in recipients
        ],
        ignore_conflicts=True,
    )

    # Keep the legacy Message.is_read flag in sync for old code paths.
    if message.is_read:
        message.is_read = False
        message.read_at = None
        message.save(update_fields=['is_read', 'read_at', 'updated_at'])

    try:
        from .views import NotificationService
        for recipient in recipients:
            NotificationService.send_message_notification(
                message=message,
                recipient=recipient,
                sound=True,
            )
    except Exception as exc:
        # A push problem must never prevent the message itself from being sent.
        logger.warning('Message notification failed for %s: %s', message.id, exc)


def _mark_conversation_read(conversation, user):
    now = timezone.now()

    MessageRecipient.objects.filter(
        message__conversation=conversation,
        recipient=user,
        is_read=False,
    ).update(is_read=True, read_at=now)

    # Direct chats have a single recipient per message, so keeping this legacy
    # flag updated preserves compatibility with older badge code.
    Message.objects.filter(
        conversation=conversation,
        is_read=False,
    ).exclude(sender=user).update(is_read=True, read_at=now)


def _message_type_for_file(uploaded_file):
    mime_type = (getattr(uploaded_file, 'content_type', '') or '').lower()
    if not mime_type:
        mime_type = (mimetypes.guess_type(uploaded_file.name)[0] or '').lower()

    if mime_type.startswith('image/'):
        return 'image'
    if mime_type.startswith('video/'):
        return 'video'
    if mime_type.startswith('audio/'):
        return 'audio'
    return 'file'


class ConversationViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        """
        Return one visible direct conversation per other user.

        Old databases can contain duplicate one-to-one Conversation rows. We do
        not destroy history here; we simply present the newest canonical row so
        the same username is not repeated in the inbox.
        """
        try:
            conversations = (
                Conversation.objects
                .filter(participants=request.user, is_active=True)
                .prefetch_related('participants')
                .annotate(participant_count=Count('participants', distinct=True))
                .order_by('-updated_at', '-created_at')
            )

            visible = []
            seen_direct_users = set()

            for conversation in conversations:
                participants = list(conversation.participants.all())
                others = [u for u in participants if u.pk != request.user.pk]

                if len(participants) == 2 and len(others) == 1:
                    other_id = str(others[0].pk)
                    if other_id in seen_direct_users:
                        continue
                    seen_direct_users.add(other_id)

                visible.append(conversation)

            serializer = ConversationSerializer(
                visible,
                many=True,
                context={'request': request},
            )
            return Response({'success': True, 'conversations': serializer.data})

        except Exception as exc:
            logger.exception('Error loading conversations: %s', exc)
            return Response(
                {'success': False, 'error': 'Error loading conversations', 'conversations': []},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        try:
            # Prefer recipient-specific state. Fall back to the legacy flag for
            # messages created before MessageRecipient was consistently used.
            recipient_count = MessageRecipient.objects.filter(
                recipient=request.user,
                is_read=False,
            ).count()

            legacy_count = Message.objects.filter(
                conversation__participants=request.user,
                is_read=False,
                recipients__isnull=True,
            ).exclude(sender=request.user).distinct().count()

            return Response({
                'success': True,
                'unread_count': recipient_count + legacy_count,
            })
        except Exception as exc:
            logger.warning('Unread-count failed: %s', exc)
            return Response({'success': True, 'unread_count': 0})

    @action(detail=False, methods=['post'], url_path='start/(?P<user_id>[^/.]+)')
    def start_conversation(self, request, user_id=None):
        target_user = get_object_or_404(CustomUser, id=user_id, is_active=True)

        if target_user.pk == request.user.pk:
            return Response(
                {'success': False, 'error': 'Cannot start a conversation with yourself.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        conversation = _direct_conversation_between(request.user, target_user)
        created = False

        if conversation is None:
            conversation = Conversation.objects.create(is_active=True)
            conversation.participants.add(request.user, target_user)
            created = True

        serializer = ConversationSerializer(conversation, context={'request': request})
        return Response({
            'success': True,
            'created': created,
            'conversation': serializer.data,
            'conversation_id': str(conversation.id),
            'messaging_url': f'/messaging/?conversation={conversation.id}',
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class MessageViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def _conversation(self, request, conversation_id):
        return Conversation.objects.filter(
            id=conversation_id,
            participants=request.user,
            is_active=True,
        ).prefetch_related('participants').first()

    def list(self, request, conversation_id=None):
        conversation = self._conversation(request, conversation_id)
        if not conversation:
            return Response(
                {'success': False, 'error': 'Conversation not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        messages = (
            Message.objects
            .filter(conversation=conversation)
            .select_related('sender', 'parent_message', 'original_sender')
            .prefetch_related('recipients')
            .order_by('created_at')
        )

        _mark_conversation_read(conversation, request.user)

        return Response({
            'success': True,
            'conversation': ConversationSerializer(
                conversation,
                context={'request': request},
            ).data,
            'messages': MessageSerializer(
                messages,
                many=True,
                context={'request': request},
            ).data,
        })

    @transaction.atomic
    def create(self, request, conversation_id=None):
        conversation = self._conversation(request, conversation_id)
        if not conversation:
            return Response(
                {'success': False, 'error': 'Conversation not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = MessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        content = (serializer.validated_data.get('content') or '').strip()
        if not content:
            return Response(
                {'success': False, 'error': 'Message cannot be empty.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        message = Message.objects.create(
            conversation=conversation,
            sender=request.user,
            delivered_at=timezone.now(),
            **serializer.validated_data,
        )
        _touch_conversation(conversation)
        transaction.on_commit(lambda: _create_delivery_rows_and_notify(message))

        return Response({
            'success': True,
            'message': MessageSerializer(message, context={'request': request}).data,
        }, status=status.HTTP_201_CREATED)

    @transaction.atomic
    @action(detail=False, methods=['post'], url_path='send-file')
    def send_file(self, request, conversation_id=None):
        conversation = self._conversation(request, conversation_id)
        if not conversation:
            return Response(
                {'success': False, 'error': 'Conversation not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = FileUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        uploaded_file = serializer.validated_data['file']

        message = Message.objects.create(
            conversation=conversation,
            sender=request.user,
            message_type=_message_type_for_file(uploaded_file),
            file=uploaded_file,
            file_name=uploaded_file.name,
            file_size=uploaded_file.size,
            file_mime_type=getattr(uploaded_file, 'content_type', '') or '',
            delivered_at=timezone.now(),
        )
        _touch_conversation(conversation)
        transaction.on_commit(lambda: _create_delivery_rows_and_notify(message))

        return Response({
            'success': True,
            'message': MessageSerializer(message, context={'request': request}).data,
        }, status=status.HTTP_201_CREATED)

    @transaction.atomic
    @action(detail=True, methods=['post'])
    def reply(self, request, conversation_id=None, pk=None):
        conversation = self._conversation(request, conversation_id)
        if not conversation:
            return Response({'success': False, 'error': 'Conversation not found'}, status=404)

        parent = get_object_or_404(Message, pk=pk, conversation=conversation)
        serializer = MessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        message = Message.objects.create(
            conversation=conversation,
            sender=request.user,
            parent_message=parent,
            delivered_at=timezone.now(),
            **serializer.validated_data,
        )
        _touch_conversation(conversation)
        transaction.on_commit(lambda: _create_delivery_rows_and_notify(message))

        return Response({
            'success': True,
            'message': MessageSerializer(message, context={'request': request}).data,
        }, status=201)

    @transaction.atomic
    @action(detail=True, methods=['post'])
    def forward(self, request, conversation_id=None, pk=None):
        source_conversation = self._conversation(request, conversation_id)
        if not source_conversation:
            return Response({'success': False, 'error': 'Conversation not found'}, status=404)

        original = get_object_or_404(Message, pk=pk, conversation=source_conversation)
        target_id = request.data.get('target_conversation_id')
        target = Conversation.objects.filter(
            id=target_id,
            participants=request.user,
            is_active=True,
        ).first()
        if not target:
            return Response({'success': False, 'error': 'Target conversation not found'}, status=404)

        message = Message.objects.create(
            conversation=target,
            sender=request.user,
            content=original.content,
            message_type=original.message_type,
            file=original.file,
            file_name=original.file_name,
            file_size=original.file_size,
            file_mime_type=original.file_mime_type,
            is_forwarded=True,
            original_sender=original.sender,
            delivered_at=timezone.now(),
        )
        _touch_conversation(target)
        transaction.on_commit(lambda: _create_delivery_rows_and_notify(message))

        return Response({
            'success': True,
            'message': MessageSerializer(message, context={'request': request}).data,
        }, status=201)


class UserViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def _queryset(self, request):
        return CustomUser.objects.filter(is_active=True).exclude(pk=request.user.pk).order_by('first_name', 'last_name', 'username')

    def list(self, request):
        users = self._queryset(request)[:100]
        return Response({
            'success': True,
            'users': MessagingUserSerializer(users, many=True, context={'request': request}).data,
        })

    @action(detail=False, methods=['get'])
    def search(self, request):
        query = (request.GET.get('q') or '').strip()
        if not query:
            return Response({'success': True, 'users': []})

        users = self._queryset(request).filter(
            Q(username__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
        )[:30]

        return Response({
            'success': True,
            'users': MessagingUserSerializer(users, many=True, context={'request': request}).data,
        })

    @action(detail=False, methods=['get'])
    def available(self, request):
        return self.list(request)


class UserStatusViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'])
    def set_online(self, request):
        status_obj, _ = UserStatus.objects.get_or_create(user=request.user)
        status_obj.is_online = True
        status_obj.last_seen = timezone.now()
        status_obj.save(update_fields=['is_online', 'last_seen'])
        return Response({'success': True})

    @action(detail=False, methods=['post'])
    def set_offline(self, request):
        status_obj, _ = UserStatus.objects.get_or_create(user=request.user)
        status_obj.is_online = False
        status_obj.last_seen = timezone.now()
        status_obj.typing_to = None
        status_obj.save(update_fields=['is_online', 'last_seen', 'typing_to'])
        return Response({'success': True})

    @action(detail=False, methods=['post'])
    def typing(self, request):
        conversation_id = request.data.get('conversation_id')
        is_typing = bool(request.data.get('is_typing'))
        status_obj, _ = UserStatus.objects.get_or_create(user=request.user)

        if is_typing and conversation_id:
            status_obj.typing_to = Conversation.objects.filter(
                id=conversation_id,
                participants=request.user,
            ).first()
        else:
            status_obj.typing_to = None

        status_obj.last_seen = timezone.now()
        status_obj.save(update_fields=['typing_to', 'last_seen'])
        return Response({'success': True})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_user_status(request):
    status_obj, _ = UserStatus.objects.get_or_create(user=request.user)
    status_obj.is_online = True
    status_obj.last_seen = timezone.now()
    status_obj.save(update_fields=['is_online', 'last_seen'])
    return Response({'success': True})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_status(request, user_id):
    user = get_object_or_404(CustomUser, id=user_id, is_active=True)
    status_obj, _ = UserStatus.objects.get_or_create(user=user)
    return Response({
        'success': True,
        'status': UserStatusSerializer(status_obj, context={'request': request}).data,
    })
