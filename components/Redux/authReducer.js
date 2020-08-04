import {dataApiRequest} from "../../API/dataApiRequest";

//actions
const AUTH_USER_DATA = 'AUTH_USER_DATA';

//начальные значения для инициализации state redux
let initialState = {
	"id": null,
	"login": null,
	"email": null,
	isLoggedIn: false,
};

export default (state = initialState, action) => {
	//поверхностное копирование state, принцип иммутабельности
	switch (action.type) {
		// current user in user page for getting profile
		case 'AUTH_USER_DATA':
			return {
				...state,
				...action.authUserData,
				isLoggedIn: true,
			};
		
		default:
			return state;
	}
}

// action creators
//for login in header
export const authUser = (authUserData) => ({type: AUTH_USER_DATA, authUserData});

export const authTh = () => {
	return (dispatch) => {
		dataApiRequest.authRequest().then(response => {
			if (response.data.resultCode === 0) {
				dispatch(authUser(response.data.data));
			}
		});
	}
};

