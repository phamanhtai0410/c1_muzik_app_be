from django.db.models import Q

from src.activity.models import ActivitySubscription


class Activity:
    def __init__(
        self,
        network,
        types,
        user=None,
        collection=None,
        filter_type="all",
        hide_viewed=False,
    ):
        self.network = network
        self.types = types
        self.user = user
        self.collection = collection
        self.hide_viewed = hide_viewed
        self.filter_type = filter_type

        # get filter: no source (no targeted follower) and type "self" if "self",
        # only with source (following activity) and type "follow" if "following", everything if "all"
        self.filters = {
            "self": {"source__isnull": True, "type__in": ["self", "both"]},
            "follow": {"source__isnull": False, "type__in": ["follow", "both"]},
            "all": {
                "source__isnull": True,
            },
        }
        self.filter_condition = self.filters[filter_type]

    def get_activity(self):
        activities = ActivitySubscription.objects.all()
        activities = activities.filter(**self.filter_condition)
        if self.types:
            activities = activities.filter(method__in=self.types)
        if self.user:
            activities = activities.filter(receiver__username=self.user)
        if self.collection:
            activities = activities.filter(
                Q(token_history__token__collection=self.collection)
                | Q(bids_history__token__collection=self.collection)
                | Q(user_action__token__collection=self.collection)
            )
        if self.hide_viewed:
            activities = activities.filter(is_viewed=False)
        if self.filter_type == "all":
            activities = activities.distinct(
                "token_history", "user_action", "bids_history"
            )
            # SQL does not work correctly with both distinct and order_by, so copying the queryset
            activities = ActivitySubscription.objects.filter(
                id__in=activities.values_list("id", flat=True)
            )
        return activities.order_by("-date")
