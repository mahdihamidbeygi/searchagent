from rest_framework import serializers

from core.models import SearchFeedback, SearchQuery, SearchResult


class SearchResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = SearchResult
        fields = ['id', 'title', 'content', 'source', 'relevance_score', 'created_at']

class SearchQuerySerializer(serializers.ModelSerializer):
    results = SearchResultSerializer(many=True, read_only=True)
    
    class Meta:
        model = SearchQuery
        fields = ['id', 'query', 'created_at', 'updated_at', 'results']

class SearchFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = SearchFeedback
        fields = ['id', 'result', 'feedback_type', 'comment', 'created_at']
        read_only_fields = ['user']

class SearchRequestSerializer(serializers.Serializer):
    query = serializers.CharField(max_length=1000)
    
    def validate_query(self, value):
        if not value.strip():
            raise serializers.ValidationError("Query cannot be empty")
        return value 