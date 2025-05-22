from typing import Dict, Any
import re

def validate_sentiment(response: str, **kwargs) -> Dict[str, Any]:
    """
    A simple function-based validator that checks if the response has a positive sentiment.
    This is a basic example - in practice, you might want to use a proper NLP library.
    
    Args:
        response: The text to validate
        **kwargs: Additional arguments (unused in this example)
        
    Returns:
        Dict containing validation results with keys:
        - is_valid: bool indicating if validation passed
        - error_message: str explanation if validation failed
        - hint: str with a suggestion for the LLM
    """
    # List of positive and negative words (simplified example)
    positive_words = {'good', 'great', 'excellent', 'amazing', 'wonderful', 'fantastic'}
    negative_words = {'bad', 'terrible', 'awful', 'horrible', 'poor', 'disappointing'}
    
    # Convert to lowercase and split into words
    words = set(re.findall(r'\w+', response.lower()))
    
    # Count positive and negative words
    pos_count = len(words.intersection(positive_words))
    neg_count = len(words.intersection(negative_words))
    
    # Validation logic
    is_valid = pos_count > neg_count
    
    return {
        "is_valid": is_valid,
        "error_message": None if is_valid else "Response has more negative than positive sentiment",
        "hint": "Please use more positive words in your response."
    } 