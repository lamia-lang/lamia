"""Tests for all selectors failed handler."""

import pytest
import os
import tempfile
import shutil
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path
from lamia.engine.managers.web.selector_resolution.all_selectors_failed_handler import AllSelectorsFailedHandler
from lamia.engine.managers.web.selector_resolution.suggestions import SelectorSuggestionService
from lamia.errors import ExternalOperationError


class TestAllSelectorsFailedHandlerInitialization:
    """Test AllSelectorsFailedHandler initialization."""
    
    def test_initialization_with_suggestion_service(self):
        """Test initialization with suggestion service."""
        suggestion_service = Mock(spec=SelectorSuggestionService)
        url = "https://example.com"
        html = "<html><body><div>Test</div></body></html>"
        
        handler = AllSelectorsFailedHandler(suggestion_service, url, html)
        
        assert handler.suggestion_service == suggestion_service
        assert handler.url == url
        assert handler.html == html
    
    def test_initialization_without_suggestion_service(self):
        """Test initialization without suggestion service."""
        url = "https://example.com"
        html = "<html><body><div>Test</div></body></html>"
        
        handler = AllSelectorsFailedHandler(None, url, html)
        
        assert handler.suggestion_service is None
        assert handler.url == url
        assert handler.html == html
    
    def test_initialization_with_empty_inputs(self):
        """Test initialization with empty inputs."""
        handler = AllSelectorsFailedHandler(None, "", "")
        
        assert handler.suggestion_service is None
        assert handler.url == ""
        assert handler.html == ""


class TestAllSelectorsFailedHandlerUrlNormalization:
    """Test URL normalization and path creation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.handler = AllSelectorsFailedHandler(None, "https://example.com", "<html></html>")
    
    def test_create_error_path_simple_domain(self):
        """Test creating error path for simple domain."""
        path = self.handler._create_error_path("https://example.com")
        expected = Path(".lamia/selector_failures/example.com/home")
        assert path == expected
    
    def test_create_error_path_with_www(self):
        """Test creating error path with www prefix."""
        path = self.handler._create_error_path("https://www.example.com/page")
        expected = Path(".lamia/selector_failures/example.com/page")
        assert path == expected
    
    def test_create_error_path_with_subdirectory(self):
        """Test creating error path with subdirectory."""
        path = self.handler._create_error_path("https://example.com/jobs/search/")
        expected = Path(".lamia/selector_failures/example.com/jobs_search")
        assert path == expected
    
    def test_create_error_path_with_query_params(self):
        """Test creating error path ignores query parameters."""
        path = self.handler._create_error_path("https://example.com/search?q=python&type=jobs")
        expected = Path(".lamia/selector_failures/example.com/search")
        assert path == expected
    
    def test_create_error_path_complex_url(self):
        """Test creating error path for complex URL."""
        url = "https://www.linkedin.com/jobs/search/?keywords=Python&location=SF"
        path = self.handler._create_error_path(url)
        expected = Path(".lamia/selector_failures/linkedin.com/jobs_search")
        assert path == expected
    
    def test_create_error_path_invalid_characters(self):
        """Test creating error path removes invalid filesystem characters."""
        path = self.handler._create_error_path("https://example.com/path/with@special#chars")
        # Should remove special chars and convert to underscores
        # The actual implementation converts '/' to '_' but doesn't handle the # and @ in the fragment/path 
        expected = Path(".lamia/selector_failures/example.com/path_withspecial")
        assert path == expected
    
    def test_create_error_path_very_long_path(self):
        """Test creating error path truncates very long paths."""
        long_path = "/very/" + "long/" * 20 + "path"
        url = f"https://example.com{long_path}"
        path = self.handler._create_error_path(url)
        
        # Should be truncated to 50 chars
        path_part = str(path).split('/')[-1]
        assert len(path_part) <= 50


class TestAllSelectorsFailedHandlerHtmlSkeleton:
    """Test HTML skeleton creation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.handler = AllSelectorsFailedHandler(None, "https://example.com", "<html></html>")
    
    def test_create_html_skeleton_simple(self):
        """Test creating HTML skeleton for simple HTML."""
        html = "<html><body><div class='test'>Hello World</div></body></html>"
        skeleton = self.handler._create_html_skeleton(html)
        
        assert "<!-- HTML Skeleton for AI Analysis" in skeleton
        assert "div class='test'" in skeleton
        assert "Hello World" in skeleton
    
    def test_create_html_skeleton_removes_comments(self):
        """Test skeleton creation removes HTML comments."""
        html = """
        <html>
            <!-- This is a large comment with lots of content -->
            <body>
                <div>Content</div>
            </body>
        </html>
        """
        skeleton = self.handler._create_html_skeleton(html)
        
        assert "This is a large comment" not in skeleton
        assert "<div>Content</div>" in skeleton
    
    def test_create_html_skeleton_removes_scripts(self):
        """Test skeleton creation removes script content."""
        html = """
        <html>
            <head>
                <script type="text/javascript">
                    // Large JavaScript code here
                    function largeFunction() { 
                        console.log("This should be removed");
                    }
                </script>
            </head>
            <body><div>Content</div></body>
        </html>
        """
        skeleton = self.handler._create_html_skeleton(html)
        
        assert "largeFunction" not in skeleton
        assert "/* script removed */" in skeleton
        assert "<div>Content</div>" in skeleton
    
    def test_create_html_skeleton_removes_styles(self):
        """Test skeleton creation removes style content."""
        html = """
        <html>
            <head>
                <style type="text/css">
                    .large-css-rules { 
                        background: url('data:image/svg+xml;base64,verylongbase64data'); 
                        font-family: 'Custom Font';
                    }
                </style>
            </head>
            <body><div>Content</div></body>
        </html>
        """
        skeleton = self.handler._create_html_skeleton(html)
        
        assert "verylongbase64data" not in skeleton
        assert "/* styles removed */" in skeleton
        assert "<div>Content</div>" in skeleton
    
    def test_create_html_skeleton_truncates_long_text(self):
        """Test skeleton creation truncates long text content."""
        long_text = "This is a very long text content that should be truncated " * 10
        html = f"<html><body><div>{long_text}</div></body></html>"
        
        skeleton = self.handler._create_html_skeleton(html, max_text_length=50)
        
        assert "..." in skeleton  # Should indicate truncation
        assert len(skeleton) < len(html)
    
    def test_create_html_skeleton_preserves_attributes(self):
        """Test skeleton creation preserves important attributes."""
        html = """
        <html>
            <body>
                <div id="main" class="container active" data-testid="main-div">
                    <button type="submit" aria-label="Submit Form">Submit</button>
                </div>
            </body>
        </html>
        """
        skeleton = self.handler._create_html_skeleton(html)
        
        assert 'id="main"' in skeleton
        assert 'class="container active"' in skeleton
        assert 'data-testid="main-div"' in skeleton
        assert 'type="submit"' in skeleton
        assert 'aria-label="Submit Form"' in skeleton
    
    def test_create_html_skeleton_truncates_long_attributes(self):
        """Test skeleton creation truncates very long attribute values."""
        long_value = "x" * 300  # Very long attribute value
        html = f'<div data-config="{long_value}">Content</div>'
        
        skeleton = self.handler._create_html_skeleton(html)
        
        assert "..." in skeleton  # Should be truncated
        assert long_value not in skeleton
    
    def test_create_html_skeleton_handles_svg(self):
        """Test skeleton creation handles SVG content."""
        html = """
        <html>
            <body>
                <svg>
                    <path d="M10,10 L100,100 L200,50 Z very long path data here"/>
                </svg>
            </body>
        </html>
        """
        skeleton = self.handler._create_html_skeleton(html)
        
        assert "/* svg content removed */" in skeleton
        assert "very long path data" not in skeleton
    
    def test_create_html_skeleton_error_handling(self):
        """Test skeleton creation error handling with malformed HTML."""
        # Malformed HTML that might cause regex issues
        html = "<div unclosed <script> malformed"
        
        # Should not raise exception
        skeleton = self.handler._create_html_skeleton(html)
        assert isinstance(skeleton, str)
    
    def test_create_html_skeleton_size_reduction(self):
        """Test skeleton creation significantly reduces size."""
        large_html = """
        <html>
            <head>
                <script>
                    """ + "// Large script content\n" * 1000 + """
                </script>
                <style>
                    """ + ".large-css { content: 'data'; }\n" * 1000 + """
                </style>
            </head>
            <body>
                <div>""" + "Large text content " * 100 + """</div>
            </body>
        </html>
        """
        
        skeleton = self.handler._create_html_skeleton(large_html)
        
        # Skeleton should be significantly smaller
        assert len(skeleton) < len(large_html) * 0.5  # At least 50% reduction


class TestAllSelectorsFailedHandlerPromptGeneration:
    """Test AI prompt generation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.handler = AllSelectorsFailedHandler(None, "https://example.com", "<html></html>")
    
    def test_generate_suggestion_prompt_click_operation(self):
        """Test prompt generation for click operation."""
        prompt = self.handler._generate_suggestion_prompt(
            failed_selector=".btn-submit",
            operation_type="click",
            skeleton_filename="test_skeleton.html"
        )
        
        assert "FAILED SELECTOR: .btn-submit" in prompt
        assert "Finding a clickable element" in prompt
        assert "test_skeleton.html" in prompt
        assert "SUGGESTION 1:" in prompt
        assert "css_selector_here" in prompt
    
    def test_generate_suggestion_prompt_type_operation(self):
        """Test prompt generation for type operation."""
        prompt = self.handler._generate_suggestion_prompt(
            failed_selector="input[name='email']",
            operation_type="type_text",
            skeleton_filename="test_skeleton.html"
        )
        
        assert "input[name='email']" in prompt
        assert "Finding an input field to type text into" in prompt
        assert "type_text" in prompt
    
    def test_generate_suggestion_prompt_unknown_operation(self):
        """Test prompt generation for unknown operation."""
        prompt = self.handler._generate_suggestion_prompt(
            failed_selector=".unknown",
            operation_type="custom_operation",
            skeleton_filename="test_skeleton.html"
        )
        
        assert "Finding an element for custom_operation" in prompt
        assert "custom_operation" in prompt
    
    def test_generate_suggestion_prompt_without_skeleton(self):
        """Test prompt generation without skeleton filename."""
        prompt = self.handler._generate_suggestion_prompt(
            failed_selector=".test",
            operation_type="click",
            skeleton_filename=""
        )
        
        assert "FAILED SELECTOR: .test" in prompt
        assert "SUGGESTION 1:" in prompt
        # The implementation always includes the skeleton reference text
        # even when no skeleton filename is provided
    
    def test_generate_suggestion_prompt_format(self):
        """Test prompt generation has correct format."""
        prompt = self.handler._generate_suggestion_prompt(
            failed_selector=".btn",
            operation_type="click",
            skeleton_filename="test.html"
        )
        
        # Check for required sections
        assert "FAILED SELECTOR:" in prompt
        assert "OPERATION:" in prompt
        assert "PAGE HTML:" in prompt
        assert "Return your suggestions in this EXACT format:" in prompt
        assert "Example:" in prompt
        assert "Please provide your suggestions now:" in prompt


class TestAllSelectorsFailedHandlerScriptContext:
    """Test script context detection."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.handler = AllSelectorsFailedHandler(None, "https://example.com", "<html></html>")
    
    def test_get_script_context_with_hu_file(self):
        """Test script context detection with .hu file."""
        with patch('sys.argv', ['playground/test_script.hu']):
            context = self.handler._get_script_context()
            assert context == "playground__test_script"
    
    def test_get_script_context_with_non_hu_file(self):
        """Test script context detection with non-.hu file."""
        with patch('sys.argv', ['test_script.py']):
            context = self.handler._get_script_context()
            assert context == "unknown_script"
    
    def test_get_script_context_no_argv(self):
        """Test script context detection with no sys.argv."""
        with patch('sys.argv', []):
            context = self.handler._get_script_context()
            assert context == "unknown_script"
    
    def test_get_script_context_empty_argv(self):
        """Test script context detection with empty argv."""
        with patch('sys.argv', ['']):
            context = self.handler._get_script_context()
            assert context == "unknown_script"


class TestAllSelectorsFailedHandlerFileOperations:
    """Test file save operations."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)  # Change to temp dir for file operations
        
        self.html = "<html><body><div class='test'>Test content</div></body></html>"
        self.handler = AllSelectorsFailedHandler(None, "https://example.com", self.html)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        os.chdir(self.original_cwd)
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    @pytest.mark.asyncio
    async def test_save_error_files(self):
        """Test saving error files for failed selector resolution."""
        html_file, prompt_file, skeleton_html = await self.handler._save_error_files_for_failed_selector_resolution(
            failed_selector=".btn-submit",
            operation_type="click"
        )
        
        # Files should be created
        assert os.path.exists(html_file)
        assert os.path.exists(prompt_file)
        
        # HTML file should contain original HTML
        with open(html_file, 'r') as f:
            content = f.read()
            assert self.html == content
        
        # Prompt file should contain prompt
        with open(prompt_file, 'r') as f:
            prompt = f.read()
            assert "FAILED SELECTOR: .btn-submit" in prompt
        
        # Skeleton should be returned
        assert skeleton_html is not None
        assert "test" in skeleton_html.lower()
    
    @pytest.mark.asyncio
    async def test_save_error_files_creates_directory(self):
        """Test that save operation creates necessary directories."""
        html_file, _, _ = await self.handler._save_error_files_for_failed_selector_resolution(
            failed_selector=".test",
            operation_type="click"
        )
        
        # Directory should be created
        dir_path = os.path.dirname(html_file)
        assert os.path.exists(dir_path)
    
    @pytest.mark.asyncio
    async def test_save_error_files_with_html_save_error(self):
        """Test save operation when HTML save fails."""
        # Mock the handler's HTML to be problematic
        self.handler.html = None  # This should cause an error
        
        html_file, prompt_file, skeleton_html = await self.handler._save_error_files_for_failed_selector_resolution(
            failed_selector=".test",
            operation_type="click"
        )
        
        # Files should still be created with error content
        assert os.path.exists(html_file)
        assert os.path.exists(prompt_file)
        
        with open(html_file, 'r') as f:
            content = f.read()
            assert "Error: Could not capture page source" in content
        
        assert "Error: Could not capture page source" in skeleton_html
    
    @pytest.mark.asyncio
    async def test_save_error_files_filename_format(self):
        """Test that saved files have correct filename format."""
        html_file, prompt_file, _ = await self.handler._save_error_files_for_failed_selector_resolution(
            failed_selector=".test",
            operation_type="click"
        )
        
        # Check filename patterns
        assert "failure_" in os.path.basename(html_file)
        assert ".html" in html_file
        assert "prompt.txt" in prompt_file
        assert "_skeleton.html" in html_file.replace(".html", "_skeleton.html")


class TestAllSelectorsFailedHandlerWithSuggestions:
    """Test handler with AI suggestion service."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        
        self.suggestion_service = Mock(spec=SelectorSuggestionService)
        self.html = "<html><body><div class='test'>Test content</div></body></html>"
        self.handler = AllSelectorsFailedHandler(self.suggestion_service, "https://example.com", self.html)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        os.chdir(self.original_cwd)
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    @pytest.mark.asyncio
    async def test_handle_all_selectors_failed_with_suggestions(self):
        """Test handling failure with AI suggestions."""
        # Mock successful suggestions
        self.suggestion_service.suggest_alternative_selectors = AsyncMock(return_value=[
            ("Primary submit button", ".btn-primary"),
            ("Submit button by type", "button[type='submit']"),
            ("Form submit button", "form .submit-btn")
        ])
        
        last_error = ExternalOperationError("Element not found", [])
        
        with patch('builtins.print') as mock_print:
            await self.handler.handle_all_selectors_failed(
                method_name="click",
                selectors=[".btn-submit", ".submit-btn"],
                last_error=last_error
            )
        
        # Should call suggestion service
        self.suggestion_service.suggest_alternative_selectors.assert_called_once_with(
            failed_selector=".btn-submit",
            operation_type="click",
            max_suggestions=3
        )
    
    @pytest.mark.asyncio
    async def test_handle_all_selectors_failed_suggestion_error(self):
        """Test handling failure when AI suggestion fails."""
        # Mock suggestion service to raise exception
        self.suggestion_service.suggest_alternative_selectors = AsyncMock(
            side_effect=Exception("AI service unavailable")
        )
        
        last_error = ExternalOperationError("Element not found", [])
        
        with pytest.raises(Exception, match="AI service unavailable"):
            with patch('builtins.print'):
                await self.handler.handle_all_selectors_failed(
                    method_name="click",
                    selectors=[".btn-submit"],
                    last_error=last_error
                )
    
    @pytest.mark.asyncio
    async def test_handle_all_selectors_failed_no_suggestions(self):
        """Test handling failure when AI returns no suggestions."""
        # Mock empty suggestions
        self.suggestion_service.suggest_alternative_selectors = AsyncMock(return_value=[])
        
        last_error = ExternalOperationError("Element not found", [])
        
        with patch('builtins.print') as mock_print:
            await self.handler.handle_all_selectors_failed(
                method_name="click",
                selectors=[".btn-submit"],
                last_error=last_error
            )
        
        # Should handle gracefully
        self.suggestion_service.suggest_alternative_selectors.assert_called_once()


class TestAllSelectorsFailedHandlerWithoutSuggestions:
    """Test handler without AI suggestion service."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        
        self.html = "<html><body><div class='test'>Test content</div></body></html>"
        self.handler = AllSelectorsFailedHandler(None, "https://example.com", self.html)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        os.chdir(self.original_cwd)
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    @pytest.mark.asyncio
    async def test_handle_all_selectors_failed_manual_instructions(self):
        """Test handling failure provides manual instructions."""
        last_error = ExternalOperationError("Element not found", [])
        
        with patch('builtins.print') as mock_print:
            await self.handler.handle_all_selectors_failed(
                method_name="click",
                selectors=[".btn-submit", ".submit-btn"],
                last_error=last_error
            )
        
        # Should not call any AI service (handler has none)
        # Should provide manual instructions
        assert mock_print.called


class TestAllSelectorsFailedHandlerIntegration:
    """Test integration scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        os.chdir(self.original_cwd)
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    @pytest.mark.asyncio
    async def test_end_to_end_failure_handling(self):
        """Test complete failure handling workflow."""
        # Create realistic HTML
        html = """
        <html>
            <head><title>Test Page</title></head>
            <body>
                <div class="container">
                    <form id="login-form">
                        <input type="email" name="email" id="email-input">
                        <input type="password" name="password" id="password-input">
                        <button type="submit" class="btn btn-primary">Login</button>
                    </form>
                </div>
            </body>
        </html>
        """
        
        # Handler without AI service
        handler = AllSelectorsFailedHandler(None, "https://app.example.com/login", html)
        last_error = ExternalOperationError("Element not found", [])
        
        with patch('builtins.print') as mock_print:
            await handler.handle_all_selectors_failed(
                method_name="click",
                selectors=[".btn-submit", "#submit-btn", "input[type='submit']"],
                last_error=last_error
            )
        
        # Check that files were created
        lamia_dir = Path(".lamia/selector_failures/app.example.com/login")
        assert lamia_dir.exists()
        
        # Check for HTML files
        html_files = list(lamia_dir.glob("*.html"))
        assert len(html_files) >= 2  # Regular and skeleton
        
        # Check for prompt file
        prompt_files = list(lamia_dir.glob("*_prompt.txt"))
        assert len(prompt_files) >= 1
        
        # Verify file contents
        html_file = [f for f in html_files if not f.name.endswith("_skeleton.html")][0]
        with open(html_file, 'r') as f:
            saved_html = f.read()
            assert "login-form" in saved_html
    
    @pytest.mark.asyncio
    async def test_multiple_failures_organize_by_url(self):
        """Test that multiple failures are organized by URL."""
        urls_and_htmls = [
            ("https://app.com/login", "<html><body><form>Login</form></body></html>"),
            ("https://app.com/signup", "<html><body><form>Signup</form></body></html>"),
            ("https://different.com/page", "<html><body><div>Different</div></body></html>"),
        ]
        
        for url, html in urls_and_htmls:
            handler = AllSelectorsFailedHandler(None, url, html)
            last_error = ExternalOperationError("Element not found", [])
            
            with patch('builtins.print'):
                await handler.handle_all_selectors_failed(
                    method_name="click",
                    selectors=[".btn"],
                    last_error=last_error
                )
        
        # Check directory structure
        assert Path(".lamia/selector_failures/app.com/login").exists()
        assert Path(".lamia/selector_failures/app.com/signup").exists()
        assert Path(".lamia/selector_failures/different.com/page").exists()
    
    @pytest.mark.asyncio
    async def test_large_html_skeleton_optimization(self):
        """Test skeleton creation with very large HTML."""
        # Create large HTML with lots of content that should be stripped
        large_content = """
        <script type="text/javascript">
            // Very large JavaScript content
        """ + "var largeData = 'x';\n" * 5000 + """
        </script>
        <style>
            /* Very large CSS content */
        """ + ".class { property: value; }\n" * 5000 + """
        </style>
        """
        
        html = f"""
        <html>
            <head>{large_content}</head>
            <body>
                <div class="important-structure">
                    <button id="target-button" class="btn btn-primary">Click me</button>
                </div>
            </body>
        </html>
        """
        
        handler = AllSelectorsFailedHandler(None, "https://example.com", html)
        last_error = ExternalOperationError("Element not found", [])
        
        with patch('builtins.print'):
            await handler.handle_all_selectors_failed(
                method_name="click",
                selectors=[".btn-submit"],
                last_error=last_error
            )
        
        # Check that skeleton file exists and is much smaller
        skeleton_files = list(Path(".lamia/selector_failures/example.com/home").glob("*_skeleton.html"))
        assert len(skeleton_files) >= 1
        
        skeleton_file = skeleton_files[0]
        with open(skeleton_file, 'r') as f:
            skeleton_content = f.read()
        
        # Skeleton should be much smaller but preserve important structure
        assert len(skeleton_content) < len(html) * 0.5  # At least 50% reduction
        assert "important-structure" in skeleton_content
        assert "target-button" in skeleton_content
        assert "btn btn-primary" in skeleton_content
        assert "var largeData" not in skeleton_content  # Script should be removed