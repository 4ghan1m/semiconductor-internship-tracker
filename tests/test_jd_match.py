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
    def test_electronics_and_software_major_not_B(self):
        result=classify(job("DFT Verification intern","Requirements: Currently pursuing a Master degree in Electrical Engineering, Electronics, Computer Engineering, Computer Science or related discipline. Testing and quality work."))
        self.assertEqual(result["match_grade"],"C")
    def test_auto_battery_sector(self):
        result=classify(job("Intern_Battery R&D/锂离子电池电芯研发实习生","岗位要求：专业要求：材料工程；硕士在读。"))
        self.assertEqual(result["industry"],"汽车")
    def test_missing_jd_not_automatically_B(self):
        result=classify(job("材料工艺实习生",""))
        self.assertEqual(result["match_grade"],"U")
    def test_graduation_unknown_flagged(self):
        result=classify(job("工艺实习生-2027届","岗位要求：专业要求：材料工程；2027届硕士。"))
        self.assertEqual(result["match_grade"],"A")
        self.assertTrue(any("毕业届别" in x for x in result["skill_gaps"]))
    def test_english_material_major_and_source(self):
        result=classify(job("Intern_Battery R&D", "Key Qualifications: basic electrochemistry. Education: Degree: Bachelor or above. Major: Material, Chemistry or Chemical Engineering. Internship: 6 months, 4-5 days/week.",source="web") | {"jd_source_url":"https://example.org/third-party-jd"})
        self.assertEqual(result["match_grade"],"A")
        self.assertEqual(result["jd_source_url"],"https://example.org/third-party-jd")
        self.assertNotEqual(result["attendance_requirement"],"未说明")
    def test_materials_major_in_education_background_is_A(self):
        result=classify(job("可靠性实习生","任职要求：教育背景：本科及以上在读，微电子、材料、自动化、电子工程等相关专业。每周出勤4天。职责：芯片可靠性和失效分析。"))
        self.assertEqual(result["match_grade"],"A")
        self.assertEqual(result["industry"],"半导体")
    def test_company_boilerplate_not_education_background(self):
        result=classify(job("行政实习生","公司介绍：本企业主营材料与芯片制造。任职要求：擅长行政工作，沟通能力强。"))
        self.assertNotEqual(result["match_grade"],"A")
    def test_university_semi_equipment_is_B(self):
        result=classify(job("半导体设备工程师（实习）","岗位要求：专业要求：机械、自动化、微电子、电气、物理化学等理工科；本科大四优先，英语四级。"))
        self.assertEqual(result["match_grade"],"B")
    def test_city_strict(self):
        self.assertTrue(is_beijing({"location":"Shanghai, CHN / Beijing, CHN"}))
        self.assertFalse(is_beijing({"location":"上海"}))
        self.assertFalse(is_beijing({"location":"待核实"}))
if __name__=="__main__":
    unittest.main()
