import React from "react";
import s from '../../css/feedback.module.css';
// import commas from '../img/commas.svg'

const Feedback = () => {
	return (
		<div className={s.grid}>
			<div className={s.img}>
			
			</div>
			<div className={s.info_box}>
				<h2>RMS делает сайты которые гарантированно работают и приносят доход</h2>
				<span className={s.info_box_txt}>Команда RMS делает эффективные сайты. Сначала я скачала их руководство, которое помогло улучшить продажи и исправить ошибки, но потом захотелось большего и я заказала дизайн сайта. Результаты меня очень обрадовали! Продажи выросли более чем в 2 раза.</span>
				<div>
					<span>Екатерина Субботина</span>
					<span>Индивидуальный предприниматель</span>
				</div>
			</div>
		</div>
	)
};

export default Feedback