"""Regression tests for JD sections without Chinese colons."""
import unittest
from jd_match import classify

class AIForMaterialsJDTests(unittest.TestCase):
    def test_material_major_in_first_numbered_requirement(self):
        jd = (
            "岗位职责：参与汽车材料数据库与机器学习性能预测。 "
            "任职要求 1. 材料科学、化学、物理、电化学、计算材料学、计算机等相关专业。 "
            "2. 熟练使用Python、pymatgen或ASE。 "
            "3. 有PyTorch经验，了解图神经网络。 "
            "4. 有VASP或LAMMPS实际经验。 "
        )
        job = {"title": "AI新材料设计工程师（实习）", "company": "北京汽车研究总院有限公司",
               "location": "北京", "description": jd, "url": "https://example.org/123"}
        result = classify(job)
        self.assertEqual(result["match_grade"], "A")
        self.assertEqual(result["industry"], "汽车")
        self.assertIn("材料", result["major_evidence"])
        self.assertTrue(any("DFT/MD" in gap for gap in result["skill_gaps"]))
        self.assertIn("PyTorch", result["hard_skills"])

    def test_marketing_materials_does_not_count_as_major(self):
        jd = "公司介绍：本企业从事材料AI。任职要求 1. 具备良好的沟通能力。2. 熟悉办公软件。"
        job = {"title": "运营实习生", "company": "北京汽车研究总院有限公司",
               "location": "北京", "description": jd, "url": "https://example.org/456"}
        self.assertNotEqual(classify(job)["match_grade"], "A")

if __name__ == "__main__":
    unittest.main()
