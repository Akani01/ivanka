from allauth.account.adapter import DefaultAccountAdapter


class OppoGlobeAccountAdapter(DefaultAccountAdapter):

    def add_message(
        self,
        request,
        level,
        message_template,
        message_context=None,
        extra_tags=""
    ):
        if message_template == "account/messages/logged_in.txt":
            return

        return super().add_message(
            request,
            level,
            message_template,
            message_context,
            extra_tags
        )