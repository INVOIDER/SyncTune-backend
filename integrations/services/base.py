class BaseMusicService:
    provider_code = None

    def get_authorization_url(self):
        raise NotImplementedError

    def fetch_token(self, code):
        raise NotImplementedError

    def get_user_profile(self, token):
        raise NotImplementedError