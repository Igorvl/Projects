import React from 'react';
import s from '../../../../../css/Post.module.css';
import icon from '../../../../../Images/logo.svg'

export default (props) => {
	return (
		<div className={s.mainBlock}>
			<img src={icon} alt=""/>
			<p>{props.msg}</p>
			<div>
				<button>Like</button> <span>{props.like}</span>
				<button>Dislike</button> <span>{props.dislike}</span>
			</div>
		</div>
	);
};

