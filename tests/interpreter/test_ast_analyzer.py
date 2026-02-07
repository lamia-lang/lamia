"""Tests for AST analyzer module."""

import pytest
import ast
from unittest.mock import patch, Mock
from lamia.interpreter.ast_analyzer import ActionNamespaceAnalyzer, extract_code_dependencies, create_execution_globals


class TestActionNamespaceAnalyzer:
    """Test ActionNamespaceAnalyzer AST visitor."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = ActionNamespaceAnalyzer()
    
    def test_initialization(self):
        """Test analyzer initialization."""
        analyzer = ActionNamespaceAnalyzer()
        
        assert isinstance(analyzer.used_namespaces, set)
        assert isinstance(analyzer.used_types, set)
        assert len(analyzer.used_namespaces) == 0
        assert len(analyzer.used_types) == 0
    
    def test_visit_attribute_web_namespace(self):
        """Test detection of web namespace attributes."""
        code = "web.click(element)"
        tree = ast.parse(code)
        
        self.analyzer.visit(tree)
        
        assert 'web' in self.analyzer.used_namespaces
    
    def test_visit_attribute_http_namespace(self):
        """Test detection of http namespace attributes."""
        code = "http.get('https://example.com')"
        tree = ast.parse(code)
        
        self.analyzer.visit(tree)
        
        assert 'http' in self.analyzer.used_namespaces
    
    def test_visit_attribute_file_namespace(self):
        """Test detection of file namespace attributes."""
        code = "file.read('data.txt')"
        tree = ast.parse(code)
        
        self.analyzer.visit(tree)
        
        assert 'file' in self.analyzer.used_namespaces
    
    def test_visit_attribute_db_namespace(self):
        """Test detection of db namespace attributes."""
        code = "db.query('SELECT * FROM users')"
        tree = ast.parse(code)
        
        self.analyzer.visit(tree)
        
        assert 'db' in self.analyzer.used_namespaces
    
    def test_visit_attribute_email_namespace(self):
        """Test detection of email namespace attributes."""
        code = "email.send(to='user@example.com', subject='Test')"
        tree = ast.parse(code)
        
        self.analyzer.visit(tree)
        
        assert 'email' in self.analyzer.used_namespaces
    
    def test_visit_attribute_multiple_namespaces(self):
        """Test detection of multiple namespaces."""
        code = """
web.click(button)
http.get(url)
file.write(data)
"""
        tree = ast.parse(code)
        
        self.analyzer.visit(tree)
        
        assert 'web' in self.analyzer.used_namespaces
        assert 'http' in self.analyzer.used_namespaces
        assert 'file' in self.analyzer.used_namespaces
    
    def test_visit_attribute_non_namespace(self):
        """Test that non-namespace attributes are ignored."""
        code = "obj.method()"
        tree = ast.parse(code)
        
        self.analyzer.visit(tree)
        
        assert 'obj' not in self.analyzer.used_namespaces
    
    def test_visit_attribute_nested_attribute(self):
        """Test handling of nested attribute access."""
        code = "obj.web.click()"
        tree = ast.parse(code)
        
        self.analyzer.visit(tree)
        
        # Should not detect 'web' since it's not a top-level namespace
        assert 'web' not in self.analyzer.used_namespaces
        assert 'obj' not in self.analyzer.used_namespaces
    
    def test_visit_name_command_types(self):
        """Test detection of command type names."""
        code = """
cmd = WebCommand(action=WebActionType.NAVIGATE)
llm_cmd = LLMCommand(prompt="test")
file_cmd = FileCommand(path="/test")
"""
        tree = ast.parse(code)
        
        self.analyzer.visit(tree)
        
        assert 'WebCommand' in self.analyzer.used_types
        assert 'WebActionType' in self.analyzer.used_types
        assert 'LLMCommand' in self.analyzer.used_types
        assert 'FileCommand' in self.analyzer.used_types
    
    def test_visit_name_session_function(self):
        """Test detection of session function."""
        code = "with session() as s: pass"
        tree = ast.parse(code)
        
        self.analyzer.visit(tree)
        
        assert 'session' in self.analyzer.used_namespaces
    
    def test_visit_name_files_context(self):
        """Test detection of files context manager."""
        code = "with files() as f: pass"
        tree = ast.parse(code)
        
        self.analyzer.visit(tree)
        
        assert 'files' in self.analyzer.used_namespaces
    
    def test_visit_name_general_identifiers(self):
        """Test collection of general identifier names."""
        code = """
x = MyType()
y = SomeClass
z = variable_name
"""
        tree = ast.parse(code)
        
        self.analyzer.visit(tree)
        
        # All identifiers should be collected as potential types
        assert 'MyType' in self.analyzer.used_types
        assert 'SomeClass' in self.analyzer.used_types
        assert 'variable_name' in self.analyzer.used_types
    
    def test_visit_subscript_simple(self):
        """Test detection of subscript type usage."""
        code = "HTML[Model]"
        tree = ast.parse(code)
        
        self.analyzer.visit(tree)
        
        assert 'HTML' in self.analyzer.used_types
        assert 'Model' in self.analyzer.used_types
    
    def test_visit_subscript_complex(self):
        """Test detection of complex subscript usage."""
        code = "JSON[Schema[User]]"
        tree = ast.parse(code)
        
        self.analyzer.visit(tree)
        
        assert 'JSON' in self.analyzer.used_types
        assert 'Schema' in self.analyzer.used_types
        assert 'User' in self.analyzer.used_types
    
    def test_visit_subscript_nested(self):
        """Test detection of nested subscript access."""
        code = "obj.attr[Type]"
        tree = ast.parse(code)
        
        self.analyzer.visit(tree)
        
        # Should detect the subscript type and obj name
        assert 'Type' in self.analyzer.used_types
        assert 'obj' in self.analyzer.used_types
        # 'attr' is an attribute access, not a name node, so it won't be in used_types


class TestActionNamespaceAnalyzerIntegration:
    """Test ActionNamespaceAnalyzer with realistic code patterns."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = ActionNamespaceAnalyzer()
    
    def test_realistic_web_automation_code(self):
        """Test analysis of realistic web automation code."""
        code = """
def automate_login():
    web.navigate('https://example.com')
    web.fill('#username', 'user')
    web.click('#login-button')
    result = web.get_text('.status')
    return result
"""
        tree = ast.parse(code)
        
        self.analyzer.visit(tree)
        
        assert 'web' in self.analyzer.used_namespaces
        assert len(self.analyzer.used_namespaces) == 1
    
    def test_realistic_mixed_namespaces_code(self):
        """Test analysis of code using multiple namespaces."""
        code = """
def process_data():
    data = http.get('https://api.example.com/data')
    file.write('data.json', data)
    web.navigate('dashboard.html')
    web.upload('#file-input', 'data.json')
"""
        tree = ast.parse(code)
        
        self.analyzer.visit(tree)
        
        assert 'http' in self.analyzer.used_namespaces
        assert 'file' in self.analyzer.used_namespaces
        assert 'web' in self.analyzer.used_namespaces
        assert len(self.analyzer.used_namespaces) == 3
    
    def test_realistic_validation_types_code(self):
        """Test analysis of code using validation types."""
        code = """
def validate_response(data: JSON[UserSchema]) -> HTML[PageModel]:
    user = data.parse()
    if user.is_valid():
        return render_template(user)
    raise ValidationError("Invalid user data")
"""
        tree = ast.parse(code)
        
        self.analyzer.visit(tree)
        
        expected_types = {
            'JSON', 'UserSchema', 'HTML', 'PageModel',
            'data', 'user', 'render_template', 'ValidationError'
        }
        assert expected_types.issubset(self.analyzer.used_types)
    
    def test_realistic_session_code(self):
        """Test analysis of session-based code."""
        code = """
with session(return_type=User) as s:
    s.web.navigate('/login')
    s.web.fill('#username', username)
    s.web.click('#submit')
    user_data = s.web.get_text('.profile')
"""
        tree = ast.parse(code)
        
        self.analyzer.visit(tree)
        
        assert 'session' in self.analyzer.used_namespaces
        assert 'User' in self.analyzer.used_types


class TestAnalyzeHybridFile:
    """Test extract_code_dependencies function."""
    
    def test_analyze_simple_code(self):
        """Test analysis of simple hybrid code."""
        # Create actual types (not Mocks) so isinstance() and issubclass() work
        mock_base_type = type('BaseType', (), {})
        mock_html_type = type('HTML', (mock_base_type,), {})
        
        mock_lamia_types = Mock()
        mock_lamia_types.BaseType = mock_base_type
        vars_dict = {
            'BaseType': mock_base_type,
            'HTML': mock_html_type,
            'SomeOtherClass': str  # Non-BaseType subclass
        }
        mock_lamia_types.__dict__ = vars_dict
        
        with patch('lamia.interpreter.ast_analyzer.lamia_types', mock_lamia_types), \
             patch('lamia.interpreter.ast_analyzer.BaseType', mock_base_type):
            code = "web.click(button)"
            result = extract_code_dependencies(code)
        
        assert 'namespaces' in result
        assert 'types' in result
        assert 'web' in result['namespaces']
        assert isinstance(result['types'], set)
    
    def test_analyze_with_return_types(self):
        """Test analysis with return type preprocessing."""
        # Create actual types (not Mocks) so isinstance() and issubclass() work
        mock_base_type = type('BaseType', (), {})
        mock_html_type = type('HTML', (mock_base_type,), {})
        
        mock_lamia_types = Mock()
        mock_lamia_types.BaseType = mock_base_type
        vars_dict = {'BaseType': mock_base_type, 'HTML': mock_html_type}
        mock_lamia_types.__dict__ = vars_dict
        
        with patch('lamia.interpreter.ast_analyzer.lamia_types', mock_lamia_types), \
             patch('lamia.interpreter.ast_analyzer.BaseType', mock_base_type):
            code = """
with session("test") -> HTML:
    def get_page():
        web.navigate('https://example.com')
"""
            result = extract_code_dependencies(code)
        
        assert 'web' in result['namespaces']
        assert 'session' in result['namespaces']
        assert 'HTML' in result['types']
    
    def test_analyze_complex_return_types(self):
        """Test analysis with complex return types like HTML[Model]."""
        # Create actual types (not Mocks) so isinstance() and issubclass() work
        mock_base_type = type('BaseType', (), {})
        mock_html_type = type('HTML', (mock_base_type,), {})
        
        mock_lamia_types = Mock()
        mock_lamia_types.BaseType = mock_base_type
        vars_dict = {'BaseType': mock_base_type, 'HTML': mock_html_type}
        mock_lamia_types.__dict__ = vars_dict
        
        with patch('lamia.interpreter.ast_analyzer.lamia_types', mock_lamia_types), \
             patch('lamia.interpreter.ast_analyzer.BaseType', mock_base_type):
            code = """
with session("test") -> HTML[UserModel]:
    def get_user_page():
        return web.get_page()
"""
            result = extract_code_dependencies(code)
        
        assert 'session' in result['namespaces']
        assert 'HTML' in result['types']
    
    def test_analyze_syntax_error(self):
        """Test fallback behavior on syntax error."""
        # Create actual types (not Mocks) so isinstance() and issubclass() work
        mock_base_type = type('BaseType', (), {})
        mock_html_type = type('HTML', (mock_base_type,), {})
        mock_json_type = type('JSON', (mock_base_type,), {})
        
        mock_lamia_types = Mock()
        mock_lamia_types.BaseType = mock_base_type
        vars_dict = {
            'BaseType': mock_base_type,
            'HTML': mock_html_type,
            'JSON': mock_json_type
        }
        mock_lamia_types.__dict__ = vars_dict
        
        with patch('lamia.interpreter.ast_analyzer.lamia_types', mock_lamia_types), \
             patch('lamia.interpreter.ast_analyzer.BaseType', mock_base_type):
            # Invalid syntax should trigger fallback
            code = "def invalid syntax:"
            with pytest.raises(SyntaxError):
                extract_code_dependencies(code)
    
    def test_analyze_comment_only_code(self):
        """Test analysis of comment-only code."""
        code = """
# This is a comment
# Another comment
"""
        result = extract_code_dependencies(code)
        
        assert 'namespaces' in result
        assert 'types' in result


class TestCreateExecutionGlobals:
    """Test create_execution_globals function."""
    
    @patch('lamia.interpreter.ast_analyzer.lamia_types')
    def test_create_globals_web_namespace(self, mock_lamia_types):
        """Test creation of globals with web namespace."""
        # Mock lamia_types
        mock_base_type = Mock()
        mock_lamia_types.BaseType = mock_base_type
        mock_lamia_types.__dict__ = {'BaseType': mock_base_type}
        
        with patch('lamia.actions.web') as mock_web:
            with patch('lamia.interpreter.commands.WebCommand') as mock_web_cmd:
                with patch('lamia.interpreter.commands.WebActionType') as mock_web_action:
                    used_namespaces = {'web'}
                    used_types = set()
                    
                    globals_dict = create_execution_globals(used_namespaces, used_types)
        
        assert 'web' in globals_dict
        assert 'WebCommand' in globals_dict
        assert 'WebActionType' in globals_dict
        assert 'InputType' in globals_dict  # Always injected
    
    @patch('lamia.interpreter.ast_analyzer.lamia_types')
    def test_create_globals_http_namespace(self, mock_lamia_types):
        """Test creation of globals with http namespace."""
        mock_base_type = Mock()
        mock_lamia_types.BaseType = mock_base_type
        mock_lamia_types.__dict__ = {'BaseType': mock_base_type}
        
        with patch('lamia.actions.http') as mock_http:
            used_namespaces = {'http'}
            used_types = set()
            
            globals_dict = create_execution_globals(used_namespaces, used_types)
        
        assert 'http' in globals_dict
        assert 'InputType' in globals_dict
    
    @patch('lamia.interpreter.ast_analyzer.lamia_types')
    def test_create_globals_file_namespace(self, mock_lamia_types):
        """Test creation of globals with file namespace."""
        mock_base_type = Mock()
        mock_lamia_types.BaseType = mock_base_type
        mock_lamia_types.__dict__ = {'BaseType': mock_base_type}
        
        with patch('lamia.actions.file') as mock_file:
            used_namespaces = {'file'}
            used_types = set()
            
            globals_dict = create_execution_globals(used_namespaces, used_types)
        
        assert 'file' in globals_dict
        assert 'InputType' in globals_dict
    
    @patch('lamia.interpreter.ast_analyzer.lamia_types')
    def test_create_globals_files_context(self, mock_lamia_types):
        """Test creation of globals with files context manager."""
        mock_base_type = Mock()
        mock_lamia_types.BaseType = mock_base_type
        mock_lamia_types.__dict__ = {'BaseType': mock_base_type}
        
        with patch('lamia.engine.managers.llm.files_context_manager.files') as mock_files:
            used_namespaces = {'files'}
            used_types = set()
            
            globals_dict = create_execution_globals(used_namespaces, used_types)
        
        assert 'files' in globals_dict
        assert 'InputType' in globals_dict
    
    @patch('lamia.interpreter.ast_analyzer.lamia_types')
    def test_create_globals_session_namespace(self, mock_lamia_types):
        """Test creation of globals with session namespace."""
        mock_base_type = Mock()
        mock_lamia_types.BaseType = mock_base_type
        mock_lamia_types.__dict__ = {'BaseType': mock_base_type}
        
        with patch('lamia.adapters.web.session_context.create_session_factory') as mock_create_session:
            with patch('lamia.adapters.web.session_context.SessionSkipException') as mock_skip_exc:
                with patch('logging.getLogger') as mock_get_logger:
                    used_namespaces = {'session'}
                    used_types = set()
                    
                    globals_dict = create_execution_globals(used_namespaces, used_types)
        
        assert 'session' in globals_dict
        assert 'SessionSkipException' in globals_dict
        assert 'logger' in globals_dict
        assert 'asyncio' in globals_dict
        assert 'InputType' in globals_dict
    
    @patch('lamia.interpreter.ast_analyzer.lamia_types')
    def test_create_globals_with_lamia_instance(self, mock_lamia_types):
        """Test creation of globals with lamia instance for session support."""
        mock_base_type = Mock()
        mock_lamia_types.BaseType = mock_base_type
        mock_lamia_types.__dict__ = {'BaseType': mock_base_type}
        
        # Mock lamia instance
        mock_lamia = Mock()
        mock_engine = Mock()
        mock_manager_factory = Mock()
        mock_web_manager = Mock()
        
        mock_lamia._engine = mock_engine
        mock_engine.manager_factory = mock_manager_factory
        mock_manager_factory.get_manager.return_value = mock_web_manager
        
        with patch('lamia.adapters.web.session_context.create_session_factory') as mock_create_session:
            with patch('lamia.interpreter.command_types.CommandType') as mock_cmd_type:
                used_namespaces = {'session'}
                used_types = set()
                
                globals_dict = create_execution_globals(used_namespaces, used_types, mock_lamia)
        
        # Verify web_manager was retrieved and passed to session factory
        mock_manager_factory.get_manager.assert_called_once()
        mock_create_session.assert_called_once_with(mock_web_manager)
    
    @patch('lamia.interpreter.ast_analyzer.lamia_types')
    def test_create_globals_command_types(self, mock_lamia_types):
        """Test creation of globals with command types."""
        mock_base_type = Mock()
        mock_lamia_types.BaseType = mock_base_type
        mock_lamia_types.__dict__ = {'BaseType': mock_base_type}
        
        with patch('lamia.interpreter.commands.WebCommand') as mock_web_cmd:
            with patch('lamia.interpreter.commands.WebActionType') as mock_web_action:
                with patch('lamia.interpreter.commands.LLMCommand') as mock_llm_cmd:
                    with patch('lamia.interpreter.commands.FileCommand') as mock_file_cmd:
                        used_namespaces = set()
                        used_types = {'WebCommand', 'WebActionType', 'LLMCommand', 'FileCommand'}
                        
                        globals_dict = create_execution_globals(used_namespaces, used_types)
        
        assert 'WebCommand' in globals_dict
        assert 'WebActionType' in globals_dict
        assert 'LLMCommand' in globals_dict
        assert 'FileCommand' in globals_dict
        assert 'InputType' in globals_dict
    
    def test_create_globals_validation_types(self):
        """Test creation of globals with validation types."""
        # Create actual types (not Mocks) so isinstance() and issubclass() work
        mock_base_type = type('BaseType', (), {})
        mock_html_type = type('HTML', (mock_base_type,), {})
        mock_json_type = type('JSON', (mock_base_type,), {})
        
        mock_lamia_types = Mock()
        mock_lamia_types.BaseType = mock_base_type
        vars_dict = {
            'BaseType': mock_base_type,
            'HTML': mock_html_type,
            'JSON': mock_json_type,
            'NotAType': str  # Not a BaseType subclass
        }
        mock_lamia_types.__dict__ = vars_dict
        
        with patch('lamia.interpreter.ast_analyzer.lamia_types', mock_lamia_types), \
             patch('lamia.interpreter.ast_analyzer.BaseType', mock_base_type):
            used_namespaces = set()
            used_types = {'HTML', 'JSON', 'NotAType'}
            
            globals_dict = create_execution_globals(used_namespaces, used_types)
        
        assert 'HTML' in globals_dict
        assert 'JSON' in globals_dict
        assert 'NotAType' not in globals_dict  # Filtered out
        assert 'InputType' in globals_dict
    
    @patch('lamia.interpreter.ast_analyzer.lamia_types')
    def test_create_globals_empty_requirements(self, mock_lamia_types):
        """Test creation of globals with no requirements."""
        mock_base_type = Mock()
        mock_lamia_types.BaseType = mock_base_type
        mock_lamia_types.__dict__ = {'BaseType': mock_base_type}
        
        used_namespaces = set()
        used_types = set()
        
        globals_dict = create_execution_globals(used_namespaces, used_types)
        
        # Should only contain InputType (always injected)
        assert 'InputType' in globals_dict
        assert len([k for k in globals_dict.keys() if not k.startswith('__')]) == 1


class TestCreateExecutionGlobalsEdgeCases:
    """Test edge cases for create_execution_globals function."""
    
    @patch('lamia.interpreter.ast_analyzer.lamia_types')
    def test_create_globals_with_exception_in_lamia_access(self, mock_lamia_types):
        """Test handling of exception when accessing lamia instance components."""
        mock_base_type = Mock()
        mock_lamia_types.BaseType = mock_base_type
        mock_lamia_types.__dict__ = {'BaseType': mock_base_type}
        
        # Mock lamia instance that raises exception when accessing engine
        mock_lamia = Mock()
        # Make _engine property raise exception when accessed
        type(mock_lamia)._engine = Mock(side_effect=AttributeError("No engine"))
        
        with patch('lamia.adapters.web.session_context.create_session_factory') as mock_create_session:
            with patch('logging.getLogger') as mock_get_logger:
                used_namespaces = {'session'}
                used_types = set()
                
                globals_dict = create_execution_globals(used_namespaces, used_types, mock_lamia)
        
        # Should still create session globals despite exception
        assert 'session' in globals_dict
        # The actual implementation catches the exception and logs a warning, but still tries to call create_session_factory
        # Let's just verify the session was created
        mock_create_session.assert_called_once()
    
    @patch('lamia.interpreter.ast_analyzer.lamia_types')
    def test_create_globals_partial_command_types(self, mock_lamia_types):
        """Test creation of globals with only some command types."""
        mock_base_type = Mock()
        mock_lamia_types.BaseType = mock_base_type
        mock_lamia_types.__dict__ = {'BaseType': mock_base_type}
        
        with patch('lamia.interpreter.commands.WebCommand') as mock_web_cmd:
            with patch('lamia.interpreter.commands.LLMCommand') as mock_llm_cmd:
                used_namespaces = set()
                used_types = {'WebCommand', 'LLMCommand'}  # Only some command types
                
                globals_dict = create_execution_globals(used_namespaces, used_types)
        
        assert 'WebCommand' in globals_dict
        assert 'LLMCommand' in globals_dict
        assert 'WebActionType' not in globals_dict  # Not in used_types
        assert 'FileCommand' not in globals_dict  # Not in used_types


class TestAnalyzeHybridFileIntegration:
    """Test integration scenarios for extract_code_dependencies."""
    
    def test_realistic_hybrid_file_analysis(self):
        """Test analysis of realistic hybrid file."""
        # Create actual types (not Mocks) so isinstance() and issubclass() work
        mock_base_type = type('BaseType', (), {})
        mock_html_type = type('HTML', (mock_base_type,), {})
        mock_json_type = type('JSON', (mock_base_type,), {})
        
        mock_lamia_types = Mock()
        mock_lamia_types.BaseType = mock_base_type
        vars_dict = {
            'BaseType': mock_base_type,
            'HTML': mock_html_type,
            'JSON': mock_json_type
        }
        mock_lamia_types.__dict__ = vars_dict
        
        with patch('lamia.interpreter.ast_analyzer.lamia_types', mock_lamia_types), \
             patch('lamia.interpreter.ast_analyzer.BaseType', mock_base_type):
            code = """
with session("scraper") -> HTML[UserProfile]:
    def scrape_user_profile(username):
        web.navigate(f'https://example.com/users/{username}')
        profile_data = web.get_text('.profile-info')
        return profile_data

def analyze_data():
    data = http.get('https://api.example.com/analytics')
    file.write('analytics.json', data)
    with session(return_type=JSON) as s:
        result = s.web.process_data()
    return result
"""
            result = extract_code_dependencies(code)
        
        expected_namespaces = {'web', 'http', 'file', 'session'}
        expected_types = {'HTML', 'UserProfile', 'JSON'}
        
        assert expected_namespaces.issubset(result['namespaces'])
        assert expected_types.intersection(result['types'])


class TestCreateExecutionGlobalsIntegration:
    """Test integration scenarios for create_execution_globals."""
    
    def test_complete_execution_environment(self):
        """Test creation of complete execution environment."""
        # Create actual types (not Mocks) so isinstance() and issubclass() work
        mock_base_type = type('BaseType', (), {})
        mock_html_type = type('HTML', (mock_base_type,), {})
        mock_json_type = type('JSON', (mock_base_type,), {})
        
        mock_lamia_types = Mock()
        mock_lamia_types.BaseType = mock_base_type
        vars_dict = {
            'BaseType': mock_base_type,
            'HTML': mock_html_type,
            'JSON': mock_json_type
        }
        mock_lamia_types.__dict__ = vars_dict
        
        with patch('lamia.interpreter.ast_analyzer.lamia_types', mock_lamia_types), \
             patch('lamia.interpreter.ast_analyzer.BaseType', mock_base_type), \
             patch('lamia.actions.web'), \
             patch('lamia.actions.http'), \
             patch('lamia.interpreter.commands.WebCommand'), \
             patch('lamia.interpreter.commands.LLMCommand'), \
             patch('lamia.adapters.web.session_context.create_session_factory'):
            used_namespaces = {'web', 'http', 'session'}
            used_types = {'HTML', 'JSON', 'WebCommand', 'LLMCommand'}
            
            globals_dict = create_execution_globals(used_namespaces, used_types)
        
        # Verify all expected globals are present
        expected_keys = {
            'web', 'http', 'session', 'HTML', 'JSON', 
            'WebCommand', 'LLMCommand', 'InputType',
            'SessionSkipException', 'logger', 'asyncio'
        }
        
        assert expected_keys.issubset(set(globals_dict.keys()))


class TestFileWriteASTAnalysis:
    """Test that File(...) triggers FileCommand + FileActionType injection."""

    def test_file_name_triggers_command_type_injection(self):
        """When 'File' appears as a Name node, FileCommand and FileActionType are added."""
        code = '''
def generate() -> File(HTML, "output.html"):
    "Generate HTML"
'''
        result = extract_code_dependencies(code)

        assert 'FileCommand' in result['types']
        assert 'FileActionType' in result['types']

    def test_create_execution_globals_injects_file_types(self):
        """FileCommand and FileActionType are available in execution globals."""
        from lamia.interpreter.commands import FileCommand, FileActionType

        used_types = {'FileCommand', 'FileActionType'}
        globals_dict = create_execution_globals(set(), used_types)

        assert globals_dict['FileCommand'] is FileCommand
        assert globals_dict['FileActionType'] is FileActionType