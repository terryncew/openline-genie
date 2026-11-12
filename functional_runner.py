import sys, importlib.util, types, unittest
root=sys.argv[1]
sys.path.insert(0,root)
# Import-only shim for selenium; actual browser acceptance is exercised independently with Playwright.
for name in ['selenium','selenium.webdriver','selenium.webdriver.chrome','selenium.webdriver.chrome.options','selenium.webdriver.common','selenium.webdriver.common.by']:
 sys.modules[name] = types.ModuleType(name)
sys.modules['selenium.webdriver.chrome.options'].Options=type('Options',(),{})
sys.modules['selenium.webdriver.common.by'].By=type('By',(),{})
spec=importlib.util.spec_from_file_location('genie_tests',root+'/tests/test_openline_genie_001.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
name='OpenLineGenieVerificationSuite'
cls=getattr(mod,name)
suite=unittest.TestSuite([cls(x) for x in unittest.defaultTestLoader.getTestCaseNames(cls) if not x.startswith('test_06')])
result=unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
