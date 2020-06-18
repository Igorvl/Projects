import React from 'react';
import s from '../../../css/Users.module.css';
import ava from '../../../Images/logo.svg';
import Icon24Like from '@vkontakte/icons/dist/24/like';
import Icon24LikeOutline from '@vkontakte/icons/dist/24/like_outline';
import * as axios from 'axios';

export default class extends React.Component {
	// ф-я жизненного цикла, вызывается только раз при первой отрисовки компонента.
	componentDidMount() {
		//запрос на сервер и производится запись пришедшего списка через getUsersCB
		axios.get('https://social-network.samuraijs.com/api/1.0/users').then(response =>
			this.props.getUsersCB(response.data.items));
	}
	
	render() {
		return (
			<div className={s.mainProfile}>
				<div>
					{this.props.usersData.map(u => {
						return (
							<div className={s.userMain}>
								<img className={s.ava} src={u.photos.small !== null ? u.photos.small : ava} alt=""/>
								<div>{u.name}</div>
								<div>
									{u.follow
										? <Icon24Like className={s.buttonFollow} onClick={() => this.props.unfollowCB(u.id)}/>
										: <Icon24LikeOutline className={s.buttonFollow} onClick={() => this.props.followCB(u.id)}/>
									}
								</div>
							</div>
						)
					})}
				</div>
			</div>
		);
	};
};
	


