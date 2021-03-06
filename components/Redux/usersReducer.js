import {dataApiRequest} from "../../API/dataApiRequest";

//actions
const GET_USERS = 'GET_USERS';
const FOLLOW = 'FOLLOW';
const UNFOLLOW = 'UNFOLLOW';
const TOTAL_PAGES = 'TOTAL_PAGES';
const CHOOSED_PAGE = 'CHOOSED_PAGE';
const CHOOSED_USERID = 'CHOOSED_USERID';
const CURRENT_USER = 'CURRENT_USER';

//начальные значения для инициализации state redux
let initialState = {
	usersData: [],
	totalUsers: 50,
	usersOnPage: 50,
	currentPage: 1,
	choosedPage: 1,
	countPages: 1,
	isPreloaderRunning: false,
	choosedUserId: 2,
	//профиль пользователя
	choosedUser: {
		"aboutMe": null,
		"contacts": {
			"facebook": null,
			"website": null,
			"vk": null,
			"twitter": null,
			"instagram": null,
			"youtube": null,
			"github": null,
			"mainLink": null
		},
		"lookingForAJob": true,
		"lookingForAJobDescription": null,
		"fullName": null,
		"userId": null,
		"photos": {
			"small": null,
			"large": null
		},
		"status": 'Statuz'
	}
};

export default (state = initialState, action) => {
	//поверхностное копирование state, принцип иммутабельности
	switch (action.type) {
		// current user in user page for getting profile
		case 'CURRENT_USER':
			return {...state, choosedUser : action.choosedUser };
		// case 'CURRENT_USER':
		// 	return {...state, choosedUser : {...state.choosedUser, ...action.choosedUser} };
		// choosed user id in user page for getting profile
		case 'CHOOSED_USERID':
			return {...state, choosedUserId: action.choosedUserId};
		// current page in pagination
		case 'CHOOSED_PAGE':
			return {...state, currentPage: state.choosedPage, choosedPage: action.choosedPage};
		// number of pages in pagination
		case 'TOTAL_PAGES':
			return {...state, countPages: Math.ceil(action.usersData.totalCount / state.usersOnPage)};
		// adding text in textarea in dialogsPage
		case 'GET_USERS':
			//возвращает копию state, и обновляет newCommentTxt
			return {
				...state,
				usersData: action.usersData.items,
				currentPage: state.choosedPage,
				countPages: Math.ceil(action.usersData.totalCount / state.usersOnPage)
			};
		
		// add new comment in dialogsPage-dialogData
		case 'FOLLOW':
			return {
				...state,
				usersData: state.usersData.map(u => {
					if (u.id === action.userId) {
						return {...u, followed: true}
					}
					return {...u}
				})
			};
		
		case 'UNFOLLOW':
			return {
				...state,
				usersData: state.usersData.map(u => {
					if (u.id === action.userId) {
						return {...u, followed: false}
					}
					return {...u}
				})
			};
		// case 'ADD_NEW_COMMENT':
		// 	//возвращает копию state, добавляет текст нового сообщения и обновляет newCommentTxt
		// 	return {...state, messageData: [...state.messageData, {id: 5, message: state.newCommentTxt}],	newCommentTxt: ""};
		
		default:
			return state;
	}
}

// action creators
//for Dialogs NewCommentText andNewComment
export const selectedPage = (choosedPage) => ({type: CHOOSED_PAGE, choosedPage});
export const totalPages = (usersData) => ({type: TOTAL_PAGES, usersData: usersData});
export const getUsers = (usersData) => ({type: GET_USERS, usersData: usersData});
export const follow = (userId) => ({type: FOLLOW, userId: userId});
export const unfollow = (userId) => ({type: UNFOLLOW, userId: userId});
export const choosedUserId = (userId) => ({type: CHOOSED_USERID, choosedUserId: userId});
export const currentUser = (user) => ({type: CURRENT_USER, choosedUser: user});


export const profileRequest = UserId => {
	return (dispatch) => {
		dataApiRequest.profileRequest(UserId).then(response => {
			dispatch(currentUser(response.data));
		})
	}
};

export const getUsersTh = (usersOnPage, choosedPage) => {
	return (dispatch) => {
		// DAL с запросом через axios пользователей с сервера
		dataApiRequest.getUsersA(usersOnPage, choosedPage).then(response => {
			dispatch(getUsers(response.data));
		})
	}
};

export const unfollowTh = (userId) => {
	return (dispatch) => {
		// DAL с запросом через axios unfollow пользователя
		dataApiRequest.setUnfollow(userId).then(() => {
			dispatch(unfollow(userId));
		});
	}
};

export const followTh = (userId) => {
	return (dispatch) => {
		// DAL с запросом через axios follow пользователя
		dataApiRequest.setFollow(userId).then(() => {
			dispatch(follow(userId))
		});
	}
};