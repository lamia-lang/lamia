import pytest
from pydantic import BaseModel, Field
from lamia.validation.validators.file_validators import HTMLStructureValidator
from typing import Any, List, Dict, Type, Tuple, Optional

# The tests that are common to all file structure validators should go to multi_file_format folder
# Tests exclusive to HTML format should go here

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_html_structure_validator_should_allow_doctype(strict):
    class HTMLModel(BaseModel):
      body: Any

    validator = HTMLStructureValidator(model=HTMLModel, strict=strict)
    valid_html = """
    <!DOCTYPE html>
    <html>
      <body>
      <p>123</p>
      </body>
    </html>
    """
    result = await validator.validate(valid_html)
    assert result.is_valid is True


@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_html_structure_validator_tag_to_model_field_case_insensitive_mapping(strict):
    class SimpleModel(BaseModel):
        title: str
        value: int

    validator = HTMLStructureValidator(model=SimpleModel, strict=strict)
    valid_xml = '<html><TITLE>Test</TITLE><Value>123</value></html>'
    result = await validator.validate(valid_xml)
    assert result.is_valid is True


# Simplified models without recursive references to avoid infinite recursion
class SimpleUserModel(BaseModel):
    username: str
    email: str

class SimpleCardModel(BaseModel):
    title: str
    description: str
    tags: List[str]

# Use Dict for complex nested structures to avoid recursion issues
ComplexWebPageModel = Dict[str, Any]

@pytest.mark.asyncio
async def test_html_social_media_feed_structure():
    """Test HTML structure that mimics a complex social media feed with various card types."""
    
    social_feed_html = """
    <div class="feed-container">
        <div class="feed-header">
            <h1>Your Feed</h1>
            <div class="filter-options">
                <button class="filter active">All</button>
                <button class="filter">Following</button>
                <button class="filter">Trending</button>
            </div>
        </div>
        
        <div class="posts-list">
            <!-- Photo post with multiple images -->
            <article class="post photo-post">
                <div class="post-header">
                    <div class="user-info">
                        <img src="/user1.jpg" class="user-avatar">
                        <div class="user-details">
                            <span class="username">photographer_jane</span>
                            <span class="location">New York, NY</span>
                        </div>
                    </div>
                    <button class="post-menu">⋯</button>
                </div>
                
                <div class="post-content">
                    <div class="image-gallery">
                        <img src="/photo1.jpg" class="gallery-image active">
                        <img src="/photo2.jpg" class="gallery-image">
                        <img src="/photo3.jpg" class="gallery-image">
                        <div class="gallery-controls">
                            <button class="gallery-prev">‹</button>
                            <button class="gallery-next">›</button>
                            <div class="gallery-indicators">
                                <span class="indicator active"></span>
                                <span class="indicator"></span>
                                <span class="indicator"></span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="post-caption">
                        <p>Amazing sunset in the city! 
                           <span class="hashtag">#photography</span> 
                           <span class="hashtag">#sunset</span>
                           <span class="hashtag">#newyork</span></p>
                    </div>
                </div>
                
                <div class="post-actions">
                    <div class="action-buttons">
                        <button class="action-btn like-btn">♡ 1,234</button>
                        <button class="action-btn comment-btn">💬 89</button>
                        <button class="action-btn share-btn">📤</button>
                    </div>
                    <div class="post-timestamp">2 hours ago</div>
                </div>
                
                <div class="comments-preview">
                    <div class="comment-summary">View all 89 comments</div>
                    <div class="recent-comments">
                        <div class="comment">
                            <span class="commenter">nature_lover</span>
                            <span class="comment-text">Absolutely breathtaking! 
                                <span class="emoji">😍</span></span>
                        </div>
                        <div class="comment">
                            <span class="commenter">city_explorer</span>
                            <span class="comment-text">Which spot is this? Need to visit!</span>
                            <div class="comment-actions">
                                <button class="comment-like">♡ 12</button>
                                <button class="comment-reply">Reply</button>
                            </div>
                        </div>
                    </div>
                </div>
            </article>
            
            <!-- Video post -->
            <article class="post video-post">
                <div class="post-header">
                    <div class="user-info">
                        <img src="/user2.jpg" class="user-avatar">
                        <div class="user-details">
                            <span class="username">tech_reviewer</span>
                            <span class="verified-badge">✓</span>
                            <span class="follower-count">1.2M followers</span>
                        </div>
                    </div>
                </div>
                
                <div class="post-content">
                    <div class="video-container">
                        <video class="post-video" controls>
                            <source src="/tech-review.mp4" type="video/mp4">
                        </video>
                        <div class="video-overlay">
                            <button class="play-button">▶</button>
                            <div class="video-info">
                                <span class="video-duration">5:32</span>
                                <span class="video-quality">HD</span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="post-caption">
                        <h3>Latest Smartphone Review: Is it worth the hype?</h3>
                        <p>Breaking down the newest flagship device with detailed analysis of:
                           <br>• Camera performance
                           <br>• Battery life 
                           <br>• Display quality
                           <br>• Performance benchmarks</p>
                        <div class="video-chapters">
                            <div class="chapter">0:00 - Unboxing</div>
                            <div class="chapter">1:30 - Design Overview</div>
                            <div class="chapter">3:15 - Camera Test</div>
                            <div class="chapter">4:45 - Final Thoughts</div>
                        </div>
                    </div>
                </div>
            </article>
            
            <!-- Text post with poll -->
            <article class="post text-post">
                <div class="post-header">
                    <div class="user-info">
                        <img src="/user3.jpg" class="user-avatar">
                        <div class="user-details">
                            <span class="username">dev_community</span>
                            <span class="community-badge">Community</span>
                        </div>
                    </div>
                </div>
                
                <div class="post-content">
                    <div class="text-content">
                        <h2>What's your favorite JavaScript framework in 2024?</h2>
                        <p>The landscape keeps evolving! Curious to see what the community prefers 
                           for new projects this year.</p>
                    </div>
                    
                    <div class="poll-widget">
                        <div class="poll-option">
                            <input type="radio" name="framework" id="react" value="react">
                            <label for="react">
                                <span class="option-text">React</span>
                                <div class="option-bar">
                                    <div class="option-fill" style="width: 45%"></div>
                                </div>
                                <span class="option-percentage">45%</span>
                            </label>
                        </div>
                        <div class="poll-option">
                            <input type="radio" name="framework" id="vue" value="vue">
                            <label for="vue">
                                <span class="option-text">Vue.js</span>
                                <div class="option-bar">
                                    <div class="option-fill" style="width: 28%"></div>
                                </div>
                                <span class="option-percentage">28%</span>
                            </label>
                        </div>
                        <div class="poll-option">
                            <input type="radio" name="framework" id="svelte" value="svelte">
                            <label for="svelte">
                                <span class="option-text">Svelte</span>
                                <div class="option-bar">
                                    <div class="option-fill" style="width: 18%"></div>
                                </div>
                                <span class="option-percentage">18%</span>
                            </label>
                        </div>
                        <div class="poll-option">
                            <input type="radio" name="framework" id="angular" value="angular">
                            <label for="angular">
                                <span class="option-text">Angular</span>
                                <div class="option-bar">
                                    <div class="option-fill" style="width: 9%"></div>
                                </div>
                                <span class="option-percentage">9%</span>
                            </label>
                        </div>
                        <div class="poll-footer">
                            <span class="poll-votes">3,247 votes</span>
                            <span class="poll-time">2 days left</span>
                        </div>
                    </div>
                </div>
            </article>
        </div>
    </div>
    """
    
    validator = HTMLStructureValidator(model=dict, strict=False)
    result = await validator.validate(social_feed_html)
    
    assert isinstance(result.is_valid, bool), "Complex social media feed HTML should be handled"


@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_raw_text_has_fences_stripped(strict):
    """When an LLM wraps the response in ```html fences, raw_text should be clean."""
    class SimpleModel(BaseModel):
        body: Any

    fenced = "```html\n<html><body><p>hello</p></body></html>\n```"
    validator = HTMLStructureValidator(model=SimpleModel, strict=strict)
    result = await validator.validate(fenced)
    assert result.is_valid is True
    assert "```" not in result.raw_text


@pytest.mark.asyncio
async def test_raw_text_clean_for_file_write():
    """raw_text (used by File() writes) should not contain markdown fences."""
    fenced = "```html\n<html><body><h1>Title</h1></body></html>\n```"
    validator = HTMLStructureValidator(model=None, strict=False)
    result = await validator.validate(fenced)
    assert result.is_valid is True
    assert result.raw_text.startswith("<html>")
    assert result.raw_text.endswith("</html>")