import unittest
from jd_match import classify
from render import is_beijing

def job(title, description, location="北京", source="web"):
    return {"title":title,"description":description,"location":location,"source":source,"company":"测试企业","url":"https://example.org/job/123"}

class JDMatchingTests(unittest.TestCase):
    def test_explicit_material_major_is_A(self):
        result=classify(job("薄膜工艺实习生","岗位要求：专业要求：材料科学与工程、冶金工程；硕士研究生在读，英语良好。"))
        self.assertEqual(result["match_grade"],"A")
    def test_energy_power_major_is_B_not_A(self):
        result=classify(job("设备工程实习生","岗位要求：专业要求：热能工程、机械工程、制冷及低温工程；硕士研究生。"))
        self.assertEqual(result["match_grade"],"B")
    def test_gpu_software_not_recommended(self):
        result=classify(job("AI GPU Compiler Intern","Requirements: major: computer science, software engineering; CUDA and GPU programming required."))
        self.assertEqual(result["match_grade"],"C")
    def test_company_boilerplate_does_not_imply_material_major(self):
        result=classify(job("Sales Intern","We are the leader in materials science. Responsibilities include selling products."))
        self.assertEqual(result["match_grade"],"U")
    def test_missing_jd_not_automatically_B(self):
        result=classify(job("材料工艺实习生",""))
        self.assertEqual(result["match_grade"],"U")
    def test_graduation_unknown_flagged(self):
        result=classify(job("工艺实习生-2027届","岗位要求：专业要求：材料工程；2027届硕士。"))
        self.assertEqual(result["match_grade"],"A")
        self.assertTrue(any("毕业届别" in x for x in result["skill_gaps"]))
    def test_city_strict(self):
        self.assertTrue(is_beijing({"location":"Shanghai, CHN / Beijing, CHN"}))
        self.assertFalse(is_beijing({"location":"上海"}))
        self.assertFalse(is_beijing({"location":"待核实"}))
if __name__=="__main__":
    unittest.main()
